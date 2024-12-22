import 'dart:io';
import 'package:path/path.dart' as path;
import 'dart:async';
import 'dart:convert';
import 'package:logging/logging.dart';
import 'config_handler.dart';
import 'package:flutter/foundation.dart';

class ServerManager {
  static final _logger = Logger('ServerManager');
  static IOSink? _logFile;
  static Process? _serverProcess;
  static bool _isRunning = false;
  static const int serverPort = 8080;
  static bool _isShuttingDown = false;
  static bool _keepAlive = true;

  static Future<void> initializeLogging() async {
    final String appDir = path.dirname(Platform.resolvedExecutable);
    final logsDir = path.join(appDir, 'logs');
    final logPath = path.join(logsDir, 'client.log');

    // Ensure logs directory exists
    await Directory(logsDir).create(recursive: true);

    // If client.log exists, rename it with timestamp
    final logFile = File(logPath);
    if (await logFile.exists()) {
      final now = DateTime.now();
      final timestamp = '${now.year}-${now.month.toString().padLeft(2, '0')}-'
          '${now.day.toString().padLeft(2, '0')}_'
          '${now.hour.toString().padLeft(2, '0')}-'
          '${now.minute.toString().padLeft(2, '0')}-'
          '${now.second.toString().padLeft(2, '0')}';

      final newLogPath = path.join(logsDir, 'client_$timestamp.log');
      await logFile.rename(newLogPath);
      _logger.info('Previous log file renamed to: $newLogPath');
    }

    // Create new log file
    _logFile = File(logPath).openWrite(mode: FileMode.write);

    Logger.root.level = Level.ALL;
    Logger.root.onRecord.listen((record) {
      final time = record.time.toIso8601String();
      final message = '[$time] ${record.level.name}: ${record.message}';

      // Write to console
      print(message);

      // Write to file
      _logFile?.writeln(message);
      if (record.error != null) {
        _logFile?.writeln('Error: ${record.error}');
      }
      if (record.stackTrace != null) {
        _logFile?.writeln('Stack trace:\n${record.stackTrace}');
      }
    });

    // Add Flutter error handling
    FlutterError.onError = (FlutterErrorDetails details) {
      _logger.severe(
        'Flutter error: ${details.exception}',
        details.exception,
        details.stack,
      );
      // Still show errors in debug mode
      FlutterError.dumpErrorToConsole(details);
    };

    // Capture uncaught async errors
    PlatformDispatcher.instance.onError = (error, stack) {
      _logger.severe('Uncaught async error', error, stack);
      return true;
    };

    _logger.info('Logging initialized. Log file: $logPath');
  }

  static Future<Process> startServer() async {
    if (_serverProcess != null) {
      _logger
          .warning('Attempting to start server while previous instance exists');
      await stopServer();
      await Future.delayed(const Duration(seconds: 2));
    }

    final envVars = ConfigHandler.getEnvVars();
    _logger.info('Starting server with environment variables configured');

    try {
      _serverProcess = await Process.start(
        'python/server/server.exe',
        [],
        environment: envVars,
        workingDirectory: await getInstallPath(),
      );

      // Add stdout and stderr logging
      _serverProcess!.stdout.transform(utf8.decoder).listen((data) {
        _logger.info('Server stdout: $data');
      });
      _serverProcess!.stderr.transform(utf8.decoder).listen((data) {
        _logger.warning('Server stderr: $data');
      });

      _isRunning = true;
      _keepAlive = true;
      _keepServerAlive();

      await _waitForServer(); // Wait for server to be ready
      return _serverProcess!;
    } catch (e, stack) {
      _logger.severe('Failed to start server', e, stack);
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

        // Actually check if the server is responding
        final isResponding = await _isServerResponding();
        if (!isResponding) {
          _logger.warning('Server not responding, attempting restart...');
          await stopServer();
          await Future.delayed(const Duration(seconds: 2));
          try {
            await startServer();
            _logger.info('Server successfully restarted');
          } catch (e) {
            _logger.severe('Failed to restart server: $e');
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
    if (_serverProcess == null) return;

    if (Platform.isWindows) {
      try {
        final result = await Process.run(
            'taskkill', ['/F', '/T', '/PID', '${_serverProcess!.pid}'],
            runInShell: true);

        _logger.info('Taskkill result: ${result.stdout}');
        if (result.exitCode != 0) {
          _logger.severe('Taskkill error: ${result.stderr}');
        }
      } catch (e) {
        _logger.severe('Failed to kill server process: $e');
        _serverProcess?.kill(ProcessSignal.sigkill);
      }
    } else {
      _serverProcess?.kill(ProcessSignal.sigkill);
    }
  }

  static Future<void> _waitForServer() async {
    _logger.info('Waiting for server to be ready...');
    final client = HttpClient();
    for (var i = 0; i < 30; i++) {
      try {
        _logger.info('Attempt ${i + 1} to connect to server...');
        final request = await client.get('localhost', serverPort, '/health');
        _logger.info('Health check request sent...');
        final response = await request.close();
        _logger.info('Health check response received: ${response.statusCode}');

        if (response.statusCode == 200) {
          await response.drain<void>();
          _logger.info('Server is ready!');
          client.close();
          return;
        }
        await response.drain<void>();
      } catch (e) {
        _logger.severe('Health check attempt failed: $e');
        await Future.delayed(const Duration(seconds: 2));
      }
    }
    client.close();
    throw Exception('Server failed to start after 30 attempts');
  }

  static bool getServerStatus() {
    return _isRunning;
  }

  // Add this method to prevent premature shutdowns
  static void preventShutdown() {
    _isShuttingDown = true;
    Future.delayed(const Duration(seconds: 30), () {
      _isShuttingDown = false;
    });
  }

  // Helper method to check if server is still responding
  static Future<bool> _isServerResponding() async {
    try {
      final client = HttpClient();
      try {
        final request = await client.get('localhost', serverPort, '/health');
        final response = await request.close();
        await response.drain<void>();
        return response.statusCode == 200;
      } on SocketException catch (e) {
        _logger.severe('Socket error during health check: ${e.message}');
        return false;
      } finally {
        client.close();
      }
    } catch (e) {
      _logger.severe('Error checking server status: $e');
      return false;
    }
  }

  static Future<void> dispose() async {
    await _logFile?.flush();
    await _logFile?.close();
  }

  static Future<String> getInstallPath() async {
    if (Platform.isWindows) {
      // Check common installation paths
      final programFiles = Platform.environment['ProgramFiles'];
      final possiblePaths = [
        path.join(programFiles ?? '', 'ScrollWise AI'),
        path.join(programFiles ?? '', 'ScrollWise'),
        path.dirname(Platform.resolvedExecutable),
      ];

      for (final dir in possiblePaths) {
        if (await Directory(dir).exists()) {
          return dir;
        }
      }
    }
    return path.dirname(Platform.resolvedExecutable);
  }
}
