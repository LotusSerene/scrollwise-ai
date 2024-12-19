import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'dart:io';
import 'dart:async';
import 'package:provider/provider.dart';
import 'package:supabase_flutter/supabase_flutter.dart' as supabase;
import 'providers/app_state.dart';
import 'screens/home_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/login_screen.dart';
import 'screens/editor_screen.dart';
import 'screens/projects_screen.dart';
import 'screens/codex_screen.dart';
import 'screens/validity_screen.dart';
import 'screens/knowledge_base_screen.dart';
import 'screens/query_screen.dart';
import 'screens/chapters_screen.dart';
import 'utils/auth.dart';
import 'utils/theme.dart';
import 'package:flutter/services.dart';
import 'providers/preset_provider.dart';
import 'providers/relationship_provider.dart';
import 'screens/timeline_screen.dart';
import 'screens/landing_screen.dart';
import 'utils/server_manager.dart';
import 'package:flutter/foundation.dart';
import 'package:logging/logging.dart';
import 'package:window_manager/window_manager.dart';

final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

bool _preventExit = true;

Future<void> main() async {
  // Ensure Flutter is initialized
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize window manager
  if (Platform.isWindows) {
    await windowManager.ensureInitialized();
    windowManager.setPreventClose(true); // Prevent default close
  }

  // Initialize logging first, before any other operations
  await ServerManager.initializeLogging();

  // Prevent the app from closing
  if (Platform.isWindows) {
    // Override the exit behavior
    ProcessSignal.sigint.watch().listen((signal) {
      // Prevent default exit behavior
      if (_preventExit) return;
    });

    ProcessSignal.sigterm.watch().listen((signal) {
      // Prevent default exit behavior
      if (_preventExit) return;
    });
  }

  try {
    await dotenv.load();
    await ServerManager.startServer();

    // Initialize Supabase
    await supabase.Supabase.initialize(
      url: dotenv.env['SUPABASE_URL'] ?? '',
      anonKey: dotenv.env['SUPABASE_ANON_KEY'] ?? '',
    );

    // Force the window to stay open
    if (Platform.isWindows) {
      await SystemChrome.setPreferredOrientations([
        DeviceOrientation.portraitUp,
        DeviceOrientation.landscapeLeft,
        DeviceOrientation.landscapeRight,
      ]);

      // Keep the event loop alive
      Timer.periodic(const Duration(milliseconds: 100), (timer) {
        if (!_preventExit) {
          timer.cancel();
          return;
        }
        WidgetsBinding.instance.scheduleFrame();
      });
    }

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
  } catch (e, stackTrace) {
    // Enhanced error logging
    Logger('main').severe('Error during initialization', e, stackTrace);
    _preventExit = false;
    runApp(
      MaterialApp(
        home: Scaffold(
          backgroundColor: Colors.black,
          body: Center(
            child: Text(
              e.toString(),
              style: const TextStyle(color: Colors.white),
              textAlign: TextAlign.center,
            ),
          ),
        ),
      ),
    );
  }
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
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    windowManager.addListener(this);

    // Add an explicit binding to keep the app alive
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        setState(() {}); // Force a rebuild to keep the app alive
      }
    });
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
    Logger('main').info('Window close requested');
    await _cleanupAndExit();
  }

  Future<void> _cleanupAndExit() async {
    Logger('main').info('Application shutting down...');
    _preventExit = false;
    await ServerManager.stopServer();
    await ServerManager.dispose();
    await windowManager.destroy();
    exit(0);
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
      initialRoute: '/',
      navigatorKey: navigatorKey,
      navigatorObservers: [
        _ServerLifecycleObserver(),
      ],
      routes: {
        '/': (context) => const AuthWrapper(),
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
      builder: (context, child) {
        // Add keyboard event handler wrapper
        return KeyboardListener(
          focusNode: FocusNode(),
          onKeyEvent: (KeyEvent event) {
            // Handle any problematic key events here
            if (event.logicalKey == LogicalKeyboardKey.altLeft) {
              // Prevent Alt key from triggering system behaviors
              return;
            }
          },
          child: child ?? const SizedBox(),
        );
      },
    );
  }
}

class AuthWrapper extends StatelessWidget {
  const AuthWrapper({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<bool>(
      future: isLoggedIn(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Scaffold(
              body: Center(child: CircularProgressIndicator()));
        } else if (snapshot.data == true) {
          return const ProjectsScreen();
        } else {
          return const LandingScreen();
        }
      },
    );
  }
}

// Add this class to handle app lifecycle
class _ServerLifecycleObserver extends NavigatorObserver {}
