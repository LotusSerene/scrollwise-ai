import 'dart:io';
import 'package:path/path.dart' as path;
import 'dart:async';
import 'package:logging/logging.dart';
import 'config_handler.dart';
import 'package:flutter/foundation.dart';

class ServerManager extends ChangeNotifier {
  static final ServerManager _instance = ServerManager._internal();
  static ServerManager get instance => _instance;

  ServerManager._internal();

  static final _logger = Logger('ServerManager');
  static IOSink? _logFile;
  static Process? _serverProcess;
  static bool _isRunning = false;
  static int serverPort = 8080;
  static bool _isShuttingDown = false;
  static bool _keepAlive = true;
  static final List<String> _allowedOrigins = [
    'http://localhost:$serverPort',
    'http://127.0.0.1:$serverPort',
  ];
  static List<int> fallbackPorts = [8081, 8082, 8083];
  static Timer? _shutdownPreventionTimer;

  static Future<void> initializeLogging() async {
    _logger.info('Starting logging initialization...');

    try {
      final String appDir = Platform.resolvedExecutable;
      _logger.info('Executable path: $appDir');

      final String parentDir = path.dirname(appDir);
      _logger.info('Parent directory: $parentDir');

      final logsDir = path.join(parentDir, 'logs');
      _logger.info('Attempting to create logs directory at: $logsDir');

      try {
        await Directory(logsDir).create(recursive: true);
        _logger.info('Logs directory created successfully');
      } catch (e) {
        _logger.severe('Error creating logs directory: $e');
        final tempDir = Directory.systemTemp;
        final tempLogsDir = path.join(tempDir.path, 'scrollwise_logs');
        _logger.info('Attempting fallback logs directory at: $tempLogsDir');
        await Directory(tempLogsDir).create(recursive: true);
      }

      final clientLogPath = path.join(logsDir, 'client.log');
      _logger.info('Log file path: $clientLogPath');

      // Handle existing client log
      final clientLogFile = File(clientLogPath);
      if (await clientLogFile.exists()) {
        final lastModified = await clientLogFile.lastModified();
        final timestamp = lastModified.toIso8601String().replaceAll(':', '-');
        final newPath = path.join(logsDir, 'client_$timestamp.log');
        await clientLogFile.rename(newPath);
        _logger.info('Renamed existing client log file to: $newPath');
      }

      try {
        _logFile = File(clientLogPath).openWrite(mode: FileMode.append);
        _logger.info('Log file opened successfully');

        // Configure root logger to capture ALL logs
        Logger.root.level = Level.ALL;
        Logger.root.onRecord.listen((record) {
          final time = record.time.toIso8601String();
          // Include logger name in the message to identify source
          final message =
              '[$time] ${record.loggerName} ${record.level.name}: ${record.message}';

          try {
            _logFile?.writeln(message);
            if (record.error != null) {
              _logFile?.writeln('Error: ${record.error}');
            }
            if (record.stackTrace != null) {
              _logFile?.writeln('Stack trace:\n${record.stackTrace}');
            }
          } catch (e) {
            _logger.severe('Error writing to log file: $e');
          }
        });

        _logger.info('Logging initialization completed');
      } catch (e) {
        _logger.severe('Error opening log file: $e');
      }
    } catch (e, stack) {
      _logger.severe('Fatal error during logging initialization: $e');
      _logger.severe('Stack trace: $stack');
    }
  }

  static Future<Process> startServer() async {
    _logger.info('Starting server process...');

    if (_serverProcess != null) {
      _logger.warning('Previous server process exists, stopping it first...');
      await stopServer();
      await Future.delayed(const Duration(seconds: 5));
    }

    final envVars = ConfigHandler.getEnvVars();
    final installPath = await getInstallPath();
    _logger.info('Install path: $installPath');

    envVars['ALLOWED_ORIGINS'] = _allowedOrigins.join(',');
    _logger.info('Allowed origins: ${envVars['ALLOWED_ORIGINS']}');

    final logDir = path.join(installPath, 'logs');
    envVars['LOG_DIR'] = logDir;
    _logger.info('Log directory set to: $logDir');

    try {
      final serverExe = path.join(installPath, 'python/server/server.exe');
      _logger.info('Server executable path: $serverExe');

      if (!await File(serverExe).exists()) {
        _logger.severe('Server executable not found at: $serverExe');
        throw Exception('Server executable not found at: $serverExe');
      }

      _logger.info('Starting server process...');
      _serverProcess = await Process.start(
        serverExe,
        [],
        environment: envVars,
        workingDirectory: installPath,
      );
      _logger.info('Server process started with PID: ${_serverProcess!.pid}');

      // Process streams without logging to client.log
      _serverProcess!.stdout.listen(
        (data) {
          // Just process the stream without logging
          String.fromCharCodes(data).trim();
        },
        onError: (error) {
          _logger.severe('Error reading stdout: $error');
        },
        cancelOnError: false,
      );

      _serverProcess!.stderr.listen(
        (data) {
          // Just process the stream without logging
          String.fromCharCodes(data).trim();
        },
        onError: (error) {
          _logger.severe('Error reading stderr: $error');
        },
        cancelOnError: false,
      );

      _isRunning = true;
      _keepAlive = true;

      await Future.delayed(const Duration(seconds: 3));
      _keepServerAlive();

      await _waitForServer();
      return _serverProcess!;
    } catch (e, stack) {
      _logger.severe('Failed to start server process', e, stack);
      throw Exception('Failed to start server: $e');
    }
  }

  static void _keepServerAlive() {
    Timer.periodic(const Duration(seconds: 60), (timer) async {
      if (!_keepAlive) {
        timer.cancel();
        return;
      }

      if (_serverProcess != null) {
        int failedChecks = 0;

        // Multiple check attempts before taking action
        for (int i = 0; i < 5; i++) {
          if (!await _isServerResponding()) {
            failedChecks++;
            await Future.delayed(const Duration(seconds: 10));
          } else {
            // Server responded, reset counter and continue monitoring
            return;
          }
        }

        // Only restart if all checks failed
        if (failedChecks == 5) {
          _logger.warning('Server unresponsive after multiple checks');
          await stopServer();
          await startServer();
        }
      }
    });
  }

  static Future<void> stopServer() async {
    if (_isShuttingDown) {
      _logger.info('Server already shutting down, skipping...');
      return;
    }

    _isShuttingDown = true;
    HttpClient? client;

    try {
      if (_serverProcess != null) {
        client = HttpClient();

        try {
          _logger.info('Sending shutdown request to server...');
          final request = await client
              .post('localhost', serverPort, '/shutdown')
              .timeout(const Duration(seconds: 5));

          final response = await request.close();
          await response.drain<void>(); // Ensure response is fully read

          if (response.statusCode == 202) {
            _logger.info('Server acknowledged shutdown request');

            // Wait for process to terminate naturally
            final deadline = DateTime.now().add(const Duration(seconds: 35));
            while (DateTime.now().isBefore(deadline)) {
              if (!await _isProcessRunning(_serverProcess!.pid)) {
                _logger.info('Server process terminated gracefully');
                _serverProcess = null;
                break;
              }
              await Future.delayed(const Duration(seconds: 1));
            }
          }
        } catch (e) {
          _logger.warning('Error sending shutdown request: $e');
        }

        // Force kill if still running
        if (_serverProcess != null) {
          _logger
              .warning('Server still running after graceful shutdown period');
          await _forceKillServer();
        }
      }
    } catch (e, stack) {
      _logger.severe('Error during server shutdown', e, stack);
    } finally {
      client?.close();
      _serverProcess = null;
      _isRunning = false;
      _isShuttingDown = false;
      await disposeResources();
    }
  }

  static Future<void> _forceKillServer() async {
    _logger.warning('Initiating force kill of server process...');
    try {
      if (Platform.isWindows) {
        // First try graceful termination
        await Process.run('taskkill', ['/PID', '${_serverProcess!.pid}']);
        await Future.delayed(const Duration(seconds: 2));

        // If still running, force kill tree
        if (await _isProcessRunning(_serverProcess!.pid)) {
          await Process.run(
              'taskkill', ['/F', '/T', '/PID', '${_serverProcess!.pid}']);
        }

        // Cleanup any orphaned processes as last resort
        await Process.run('taskkill', ['/F', '/IM', 'server.exe'],
            runInShell: true);
      } else {
        // On Unix systems, try SIGTERM first
        _serverProcess?.kill(ProcessSignal.sigterm);
        await Future.delayed(const Duration(seconds: 2));

        // If still running, try SIGKILL
        if (await _isProcessRunning(_serverProcess!.pid)) {
          _serverProcess?.kill(ProcessSignal.sigkill);

          // Kill any child processes
          await Process.run('pkill', ['-KILL', '-P', '${_serverProcess!.pid}']);
        }
      }
    } catch (e) {
      _logger.severe('Failed to force kill server: $e');
    }
  }

  // Helper method to check if a process is still running
  static Future<bool> _isProcessRunning(int pid) async {
    try {
      if (Platform.isWindows) {
        final result = await Process.run('tasklist', ['/FI', 'PID eq $pid']);
        return result.stdout.toString().contains(pid.toString());
      } else {
        final result = await Process.run('ps', ['-p', pid.toString()]);
        return result.exitCode == 0;
      }
    } catch (e) {
      _logger.warning('Error checking process status: $e');
      return false;
    }
  }

  static Future<void> _waitForServer() async {
    _logger.info('Waiting for server to be ready...');
    final client = HttpClient();
    for (var i = 0; i < 10; i++) {
      try {
        _logger.info('Health check attempt ${i + 1}/10');
        final request = await client.get('localhost', serverPort, '/health');
        _logger.info('Health check request sent');

        final response = await request.close().timeout(
              const Duration(seconds: 5),
              onTimeout: () => throw TimeoutException('Health check timed out'),
            );

        _logger.info('Health check response received: ${response.statusCode}');

        if (response.statusCode == 200) {
          await response.drain<void>();
          _logger.info('Server is ready and responding!');
          client.close();
          return;
        }

        _logger.warning('Unexpected status code: ${response.statusCode}');
        await response.drain<void>();
        await Future.delayed(const Duration(seconds: 3));
      } catch (e) {
        _logger.severe('Health check attempt ${i + 1} failed: $e');
        await Future.delayed(const Duration(seconds: 3));
      }
    }
    client.close();
    _logger.severe('Server failed to start after 10 attempts');
    throw Exception('Server failed to start after 10 attempts');
  }

  static bool getServerStatus() {
    return _isRunning;
  }

  // Add this method to prevent premature shutdowns
  static void preventShutdown(
      [Duration duration = const Duration(seconds: 30)]) {
    _shutdownPreventionTimer?.cancel();
    _isShuttingDown = true;
    _shutdownPreventionTimer = Timer(duration, () {
      _isShuttingDown = false;
    });
  }

  static void allowShutdown() {
    _shutdownPreventionTimer?.cancel();
    _isShuttingDown = false;
  }

  // Helper method to check if server is still responding
  static Future<bool> _isServerResponding() async {
    final client = HttpClient();
    try {
      final request = await client.get('localhost', serverPort, '/health');
      final response = await request.close().timeout(
            const Duration(seconds: 10),
          );

      if (response.statusCode == 200) {
        return true;
      } else if (response.statusCode == 503 || response.statusCode == 429) {
        // Consider server "busy" but alive if we get these status codes
        _logger.info('Server is busy but running');
        return true;
      }

      _logger.warning('Unexpected status code: ${response.statusCode}');
      return false;
    } on SocketException catch (e) {
      // Handle specific connection issues
      if (e.osError?.errorCode == 61 || e.osError?.errorCode == 10061) {
        // Connection refused - server likely not running
        _logger.info('Server connection refused: ${e.message}');
      } else {
        _logger.warning('Socket error during health check: ${e.message}');
      }
      return false;
    } on TimeoutException {
      // Consider server "busy" if request times out
      _logger.info('Health check timed out - server may be busy');
      return true; // Changed to return true on timeout
    } catch (e) {
      // Handle unexpected errors without assuming server is down
      _logger.severe('Unexpected error during health check: $e');
      return false;
    } finally {
      client.close();
    }
  }

  static Future<void> disposeResources() async {
    await _logFile?.flush();
    await _logFile?.close();
  }

  static Future<String> getInstallPath() async {
    return path.dirname(Platform.resolvedExecutable);
  }

  static void addAllowedOrigin(String origin) {
    if (!_allowedOrigins.contains(origin)) {
      _allowedOrigins.add(origin);
      _logger.info('Added allowed origin: $origin');
    }
  }

  static Future<int> findAvailablePort() async {
    // Try default port first
    if (await _isPortAvailable(serverPort)) return serverPort;

    // Try fallback ports
    for (var port in fallbackPorts) {
      if (await _isPortAvailable(port)) return port;
    }

    throw Exception('No available ports found');
  }

  static Future<bool> _isPortAvailable(int port) async {
    final server = await ServerSocket.bind(InternetAddress.anyIPv4, port);
    server.close();
    return true;
  }

  static void forceStop() {
    _logger.warning('Force stopping server process...');
    try {
      if (_serverProcess != null) {
        if (Platform.isWindows) {
          Process.runSync(
              'taskkill', ['/F', '/T', '/PID', '${_serverProcess!.pid}']);
        } else {
          _serverProcess!.kill(ProcessSignal.sigkill);
        }
        _serverProcess = null;
      }
      _isRunning = false;
      _keepAlive = false;
    } catch (e) {
      _logger.severe('Error during force stop: $e');
    }
  }
}
