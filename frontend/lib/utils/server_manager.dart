import 'dart:io';
import 'package:path/path.dart' as path;
import 'dart:async';
import 'package:logging/logging.dart';
import 'config_handler.dart';

class ServerManager {
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

      final serverLogPath = path.join(logDir, 'server.log');
      _serverProcess!.stdout.listen((data) {
        final message = String.fromCharCodes(data).trim();
        File(serverLogPath).writeAsString(
          '[${DateTime.now().toIso8601String()}] INFO: $message\n',
          mode: FileMode.append,
        );
      });

      _serverProcess!.stderr.listen((data) {
        final message = String.fromCharCodes(data).trim();
        File(serverLogPath).writeAsString(
          '[${DateTime.now().toIso8601String()}] ERROR: $message\n',
          mode: FileMode.append,
        );
      });

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
    Timer.periodic(const Duration(seconds: 5), (timer) async {
      if (!_keepAlive) {
        timer.cancel();
        return;
      }

      if (_serverProcess != null) {
        _logger.info('Server heartbeat check - PID: ${_serverProcess!.pid}');
        final isResponding = await _isServerResponding();
        if (!isResponding) {
          _logger.warning('Server connection lost, attempting restart');
          await stopServer();
          await Future.delayed(const Duration(seconds: 2));
          try {
            await startServer();
            _logger.info('Server process restarted');
          } catch (e) {
            _logger.severe('Failed to restart server process', e);
          }
        } else {
          _logger.info('Server health check successful');
        }
      }
    });
  }

  static Future<void> stopServer() async {
    if (_isShuttingDown) {
      _logger.info('Server already shutting down, skipping...');
      return;
    }

    try {
      _isShuttingDown = true;
      _keepAlive = false;
      _logger.info('Stopping server...');

      if (_serverProcess != null) {
        await _forceKillServer();
        _serverProcess = null;
      }

      _isRunning = false;
    } catch (e, stack) {
      _logger.severe('Error stopping server', e, stack);
    } finally {
      _isShuttingDown = false;
    }
  }

  // Add this helper method for force killing
  static Future<void> _forceKillServer() async {
    if (!await _isServerResponding()) {
      _logger.info('Server is unresponsive, proceeding with force kill');
      if (Platform.isWindows) {
        try {
          // Try graceful shutdown first
          _serverProcess?.kill();
          await Future.delayed(const Duration(seconds: 2));

          // Check if process is still running before force kill
          if (_serverProcess != null &&
              await _isProcessRunning(_serverProcess!.pid)) {
            final result = await Process.run(
              'taskkill',
              ['/F', '/T', '/PID', '${_serverProcess!.pid}'],
              runInShell: true,
            );

            if (result.exitCode != 0) {
              _logger.warning(
                  'Failed to kill by PID, attempting to kill server.exe');
              await Process.run(
                'taskkill',
                ['/F', '/IM', 'server.exe'],
                runInShell: true,
              );
            }
          }
        } catch (e) {
          _logger.severe('Failed to kill server process: $e');
          _serverProcess?.kill(ProcessSignal.sigkill);
        }
      } else {
        _serverProcess?.kill(ProcessSignal.sigkill);
      }

      _serverProcess = null;
      _isRunning = false;
    } else {
      _logger.info('Server is still responding, skipping force kill');
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
        const Duration(seconds: 5),
        onTimeout: () {
          _logger.warning('Health check timed out');
          throw TimeoutException('Health check timed out');
        },
      );

      // Drain response to free resources
      await response.drain<void>();

      // Consider 401/403 as "responding" since it means the server is running
      if (response.statusCode == 401 || response.statusCode == 403) {
        _logger.info('Server is running but returned ${response.statusCode}');
        return true;
      }

      return response.statusCode == 200;
    } on SocketException catch (e) {
      // Handle specific connection issues
      if (e.osError?.errorCode == 61 || e.osError?.errorCode == 10061) {
        // Connection refused - server likely not running
        _logger.info('Server connection refused: ${e.message}');
      } else {
        _logger.warning('Socket error during health check: ${e.message}');
      }
      return false;
    } on HttpException catch (e) {
      // Handle HTTP protocol errors
      _logger.warning('HTTP error during health check: $e');
      return false;
    } catch (e) {
      // Handle unexpected errors without assuming server is down
      _logger.severe('Unexpected error during health check: $e');
      return false;
    } finally {
      client.close();
    }
  }

  static Future<void> dispose() async {
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
}
