// Dart imports
import 'dart:async';
import 'dart:io';

// Flutter imports
import 'package:flutter/material.dart';
import 'package:logging/logging.dart';
import 'package:provider/provider.dart';
// Removed Supabase import
import 'package:window_manager/window_manager.dart';

// Providers
import 'providers/app_state.dart';
import 'providers/preset_provider.dart';
import 'providers/relationship_provider.dart';

// Screens
import 'screens/chapters_screen.dart';
import 'screens/codex_screen.dart';
import 'screens/editor_screen.dart';
import 'screens/home_screen.dart'; // Keep if used
import 'screens/knowledge_base_screen.dart';
// Removed LoginScreen import
import 'screens/projects_screen.dart';
import 'screens/query_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/timeline_screen.dart';
import 'screens/validity_screen.dart';

// Utils
// Removed auth.dart import (no longer needed here)
import 'utils/server_manager.dart';
import 'utils/theme.dart';

final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

bool _preventExit = true; // Keep for window close handling

Future<void> main() async {
  final log = Logger('main');
  log.info('Application starting...');

  // Start the app with a loading screen immediately
  runApp(
    const MaterialApp(
      home: Scaffold(
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Initializing...'),
            ],
          ),
        ),
      ),
    ),
  );

  try {
    log.info('Initializing Flutter bindings...');
    WidgetsFlutterBinding.ensureInitialized();

    if (Platform.isWindows) {
      log.info('Setting up window manager...');
      await windowManager.ensureInitialized();
      await windowManager.waitUntilReadyToShow();
      await windowManager.setTitle('ScrollWise AI');
      await windowManager.setPreventClose(true);
      await windowManager.show();
    }

    log.info('Starting core services...');
    await ServerManager.initializeLogging();

    // Modify the initialization block to handle errors better
    try {
      await Future.wait([
        ServerManager.startServer().timeout(
          const Duration(seconds: 30),
          onTimeout: () {
            log.warning('Server start timed out, continuing...');
            throw TimeoutException('Server start timed out');
          },
        ),
        // Removed Supabase initialization block
      ]);
    } catch (e) {
      log.severe('Service initialization failed: $e'); // Keep error handling
      _preventExit = false; // Allow exit when there's a startup error
      rethrow;
    }

    log.info('Launching main application...');

    // Launch the actual app
    runApp(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => AppState()),
          ChangeNotifierProvider(create: (_) => RelationshipProvider()),
          ChangeNotifierProvider(create: (context) => PresetProvider()),
        ],
        child: const ScrollWiseApp(),
      ),
    );

    // Removed auth state initialization block

    log.info('Application started successfully');
  } catch (e, stackTrace) {
    log.severe('Fatal error during startup', e, stackTrace);
    _preventExit = false; // Allow exit when there's a startup error
    _showErrorScreen('Startup Error: ${e.toString()}');
  }
}

// Modify the error screen to include an exit button
void _showErrorScreen(String errorMessage) {
  runApp(
    MaterialApp(
      home: Scaffold(
        backgroundColor: Colors.black,
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(
                Icons.error_outline,
                color: Colors.red,
                size: 64,
              ),
              const SizedBox(height: 16),
              Text(
                errorMessage,
                style: const TextStyle(color: Colors.white),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: () async {
                  await windowManager.destroy();
                  exit(1);
                },
                child: const Text('Exit Application'),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

// Add this class to handle Windows-specific bindings
class WindowsBindingHandler {
  static void ensureInitialized() {
    if (Platform.isWindows) {
      // Keep the Flutter engine running with just frame scheduling
      WidgetsBinding.instance.addPostFrameCallback((_) {
        WidgetsBinding.instance.scheduleFrame();
      });
    }
  }
}

class ScrollWiseApp extends StatefulWidget {
  const ScrollWiseApp({super.key});

  @override
  State<ScrollWiseApp> createState() => _ScrollWiseAppState();
}

class _ScrollWiseAppState extends State<ScrollWiseApp>
    with WidgetsBindingObserver, WindowListener {
  final log = Logger('ScrollWiseApp');

  @override
  void initState() {
    super.initState();
    log.info('Initializing ScrollWiseApp state...');
    WidgetsBinding.instance.addObserver(this);
    windowManager.addListener(this);

    // Initialize auth state when app starts
    // Removed _initializeAuth call
  }

  // Removed _initializeAuth method

  @override
  void dispose() {
    windowManager.removeListener(this);
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  // Add this window close handler
  @override
  Future<void> onWindowClose() async {
    log.info('Window close requested');
    if (_preventExit) {
      await _cleanupAndExit();
    }
  }

  Future<void> _cleanupAndExit() async {
    log.info('Starting application cleanup...');
    _preventExit = false;

    // Show shutdown screen
    runApp(
      MaterialApp(
        home: Scaffold(
          backgroundColor: Colors.black,
          body: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const CircularProgressIndicator(),
                const SizedBox(height: 16),
                const Text(
                  'Shutting down...',
                  style: TextStyle(color: Colors.white, fontSize: 18),
                ),
                const SizedBox(height: 8),
                Text(
                  'Please wait while we clean up',
                  style: TextStyle(color: Colors.white.withOpacity(0.7)),
                ),
              ],
            ),
          ),
        ),
      ),
    );

    try {
      log.info('Stopping server...');
      await ServerManager.stopServer().timeout(
        const Duration(seconds: 10),
        onTimeout: () {
          log.warning('Server stop timed out, forcing shutdown...');
          ServerManager.forceStop();
        },
      );
      log.info('Server stopped');

      await Future.delayed(const Duration(seconds: 3));

      log.info('Disposing server manager...');
      await ServerManager.disposeResources();
      log.info('Server manager disposed');

      await Future.delayed(const Duration(seconds: 1));

      log.info('Destroying window...');
      await windowManager.destroy();
      log.info('Window destroyed, exiting application');

      exit(0);
    } catch (e, stack) {
      log.severe('Error during cleanup', e, stack);
      exit(1);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.detached) {
      _cleanupAndExit(); // Add cleanup here too
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ScrollWise AI',
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.dark,
      navigatorKey: navigatorKey,
      // Start directly at the ProjectsScreen (or HomeScreen if preferred)
      initialRoute: '/projects',
      routes: {
        // Define routes, LoginScreen is removed
        '/': (context) => const ProjectsScreen(), // Default route
        '/projects': (context) => const ProjectsScreen(),
        '/home': (context) => const HomeScreen(),
        '/editor': (context) => const EditorScreen(),
        // Routes requiring projectId:
        '/chapters': (context) => ChaptersScreen(
              projectId: ModalRoute.of(context)!.settings.arguments as String,
            ),
        '/codex': (context) => CodexScreen(
              projectId: ModalRoute.of(context)!.settings.arguments as String,
            ),
        '/knowledge-base': (context) => KnowledgeBaseScreen(
              projectId: ModalRoute.of(context)!.settings.arguments as String,
            ),
        '/query': (context) => QueryScreen(
              projectId: ModalRoute.of(context)!.settings.arguments as String,
            ),
        '/settings': (context) =>
            const SettingsScreen(), // Settings might not need projectId
        '/timeline': (context) => TimelineScreen(
              projectId: ModalRoute.of(context)!.settings.arguments as String,
            ),
        '/validity': (context) => ValidityScreen(
              projectId: ModalRoute.of(context)!.settings.arguments as String,
            ),
        // Removed '/login' route
      },
    );
  }
}
