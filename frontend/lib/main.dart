// Dart imports
import 'dart:async';
import 'dart:io';

// Flutter imports
import 'package:flutter/material.dart';
import 'package:logging/logging.dart';
import 'package:provider/provider.dart';
import 'package:supabase_flutter/supabase_flutter.dart' as supabase;
import 'package:window_manager/window_manager.dart';

// Providers
import 'providers/app_state.dart';
import 'providers/preset_provider.dart';
import 'providers/relationship_provider.dart';

// Screens
import 'screens/chapters_screen.dart';
import 'screens/codex_screen.dart';
import 'screens/editor_screen.dart';
import 'screens/home_screen.dart';
import 'screens/knowledge_base_screen.dart';
import 'screens/landing_screen.dart';
import 'screens/login_screen.dart';
import 'screens/projects_screen.dart';
import 'screens/query_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/timeline_screen.dart';
import 'screens/validity_screen.dart';

// Utils
import 'utils/auth.dart';
import 'utils/config_handler.dart';
import 'utils/server_manager.dart';
import 'utils/theme.dart';

final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

bool _preventExit = true;

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

    // Initialize services concurrently
    await Future.wait([
      ServerManager.startServer().timeout(
        const Duration(seconds: 30),
        onTimeout: () {
          log.warning('Server start timed out, continuing...');
          throw TimeoutException('Server start timed out');
        },
      ),
      supabase.Supabase.initialize(
        url: ConfigHandler.get('SUPABASE_URL', fallback: ''),
        anonKey: ConfigHandler.get('SUPABASE_ANON_KEY', fallback: ''),
      ).timeout(
        const Duration(seconds: 10),
        onTimeout: () {
          log.warning('Supabase initialization failed');
          throw TimeoutException('Supabase initialization failed');
        },
      ),
    ]);

    log.info('Launching main application...');

    // Launch the actual app
    runApp(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => AppState()),
          ChangeNotifierProvider(create: (_) => RelationshipProvider()),
          ChangeNotifierProvider(create: (context) => PresetProvider()),
        ],
        child: const MyApp(),
      ),
    );

    // Initialize auth state after UI is running
    Future.delayed(const Duration(seconds: 1), () async {
      try {
        final appState = navigatorKey.currentContext != null
            ? Provider.of<AppState>(navigatorKey.currentContext!, listen: false)
            : null;
        await appState?.checkAuthState();
      } catch (e) {
        log.warning('Auth initialization error: $e');
      }
    });

    log.info('Application started successfully');
  } catch (e, stackTrace) {
    log.severe('Fatal error during startup', e, stackTrace);
    _showErrorScreen('Startup Error: ${e.toString()}');
  }
}

// Helper function to show error screen
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

class MyApp extends StatefulWidget {
  const MyApp({super.key});

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp>
    with WidgetsBindingObserver, WindowListener {
  final log = Logger('MyApp');

  @override
  void initState() {
    super.initState();
    log.info('Initializing MyApp state...');
    WidgetsBinding.instance.addObserver(this);
    windowManager.addListener(this);

    // Initialize auth state when app starts
    _initializeAuth();
  }

  Future<void> _initializeAuth() async {
    try {
      await initializeAuthState();
    } catch (e) {
      log.severe('Error initializing auth state: $e');
    }
  }

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
      theme: AppTheme.darkTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.dark,
      debugShowCheckedModeBanner: false,
      navigatorKey: navigatorKey,
      home: Consumer<AppState>(
        builder: (context, appState, _) {
          return appState.isLoggedIn
              ? const ProjectsScreen()
              : const LandingScreen();
        },
      ),
      routes: {
        '/landing': (context) => const LandingScreen(),
        '/projects': (context) => const ProjectsScreen(),
        '/home': (context) => const HomeScreen(),
        '/login': (context) => LoginScreen(onLogin: (token) {
              final appState = Provider.of<AppState>(context, listen: false);
              appState.setLoggedIn(true);
              appState.setToken(token);
              Navigator.pushReplacementNamed(context, '/projects');
            }),
        '/editor': (context) => const EditorScreen(),
        '/settings': (context) => const SettingsScreen(),
        '/codex': (context) => CodexScreen(
            projectId: ModalRoute.of(context)!.settings.arguments as String),
        '/validity': (context) => ValidityScreen(
            projectId: ModalRoute.of(context)!.settings.arguments as String),
        '/knowledge_base': (context) => KnowledgeBaseScreen(
            projectId: ModalRoute.of(context)!.settings.arguments as String),
        '/query': (context) => QueryScreen(
            projectId: ModalRoute.of(context)!.settings.arguments as String),
        '/chapters': (context) => ChaptersScreen(
            projectId: ModalRoute.of(context)!.settings.arguments
                as String), // Added ChaptersScreen route
        '/timeline': (context) => TimelineScreen(
            projectId: ModalRoute.of(context)!.settings.arguments as String),
      },
    );
  }
}
