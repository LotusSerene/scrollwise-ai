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

    _logger.info('Logging initialized. Log file: $logPath');
  }

  static Future<Process> startServer() async {
    final envVars = ConfigHandler.getEnvVars();

    return await Process.start(
      'python/server/server.exe',
      [],
      environment: envVars, // Pass config values as environment variables
      workingDirectory: await getInstallPath(),
    );
  }

  static void _keepServerAlive() {
    Timer.periodic(const Duration(seconds: 5), (timer) {
      if (!_keepAlive) {
        timer.cancel();
        return;
      }
      if (_serverProcess != null) {
        _logger.info('Server heartbeat check - PID: ${_serverProcess!.pid}');
      }
    });
  }

  static Future<void> stopServer() async {
    if (_isShuttingDown) return;
    _keepAlive = false;
    if (!_isRunning) return;

    try {
      _isShuttingDown = true;
      _logger.info('Initiating server shutdown sequence...');

      // Try graceful shutdown first
      try {
        final client = HttpClient();
        final request = await client.post('localhost', serverPort, '/shutdown');
        final response = await request.close();
        await response.drain<void>();

        _logger.info('Shutdown request sent, waiting for server to stop...');

        // Wait a bit for the server to shutdown gracefully
        await Future.delayed(const Duration(seconds: 2));

        // If server is still running after graceful shutdown attempt, force kill it
        if (await _isServerResponding()) {
          _logger.warning(
              'Server still running after graceful shutdown, forcing termination...');
          await _forceKillServer();
        } else {
          _logger.info('Server stopped gracefully');
        }

        client.close();
      } catch (e) {
        _logger.warning('Graceful shutdown failed, forcing termination: $e');
        await _forceKillServer();
      }

      _isRunning = false;
      _logger.info('Server process terminated');
    } catch (e, stackTrace) {
      _logger.severe('Error during server shutdown', e, stackTrace);
    } finally {
      _isShuttingDown = false;
      _serverProcess = null;
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
