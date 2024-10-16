import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'components/header.dart';
import 'screens/login_screen.dart';
import 'screens/create_screen.dart';
import 'screens/editor_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/validity_screen.dart';
import 'screens/knowledge_base_screen.dart';
import 'screens/settings_screen.dart';
import 'utils/auth.dart' show localStorage;
import 'package:fluttertoast/fluttertoast.dart';
import 'package:provider/provider.dart';
import 'providers/app_state.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load();
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (context) => AppState(),
      child: const AppContent(),
    );
  }
}

class AppContent extends StatefulWidget {
  const AppContent({super.key});

  @override
  State<AppContent> createState() => _AppContentState();
}

class _AppContentState extends State<AppContent> {
  final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _checkLoginStatus();
    });
  }

  Future<void> _checkLoginStatus() async {
    final token = localStorage.getItem('token');
    Provider.of<AppState>(context, listen: false).setLoggedIn(token != null);
  }

  void _handleLogout() {
    localStorage.removeItem('token');
    Provider.of<AppState>(context, listen: false).setLoggedIn(false);
    navigatorKey.currentState?.pushReplacementNamed('/login');
  }

  void _handleLogin(String token) {
    localStorage.setItem('token', token);
    Provider.of<AppState>(context, listen: false).setLoggedIn(true);
    navigatorKey.currentState?.pushReplacementNamed('/dashboard');
  }

  @override
  Widget build(BuildContext context) {
    final appState = Provider.of<AppState>(context);
    return MaterialApp(
      navigatorKey: navigatorKey,
      title: 'Gemini Frontend',
      theme: ThemeData.dark().copyWith(
        primaryColor: Colors.blue, // Keep primary color as blue
        scaffoldBackgroundColor: Colors.grey[900], // Dark background
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(
              0xFF303030), // Dark app bar (equivalent to Colors.grey[850])
          titleTextStyle: TextStyle(color: Colors.white), // White title text
        ),
        textTheme: const TextTheme(
          bodyMedium: TextStyle(color: Colors.white), // White body text
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.blue, // Blue buttons
            foregroundColor: Colors.white, // White button text
          ),
        ),
      ),
      home: appState.isLoggedIn
          ? const DashboardScreen()
          : LoginScreen(onLogin: _handleLogin),
      routes: {
        '/login': (context) => LoginScreen(onLogin: _handleLogin),
        '/create': (context) => Scaffold(
              appBar: Header(
                isLoggedIn: appState.isLoggedIn,
                onLogout: _handleLogout,
                isGenerating: false,
              ),
              body: const CreateScreen(),
            ),
        '/editor': (context) => Scaffold(
              appBar: Header(
                isLoggedIn: appState.isLoggedIn,
                onLogout: _handleLogout,
                isGenerating: false,
              ),
              body: const EditorScreen(),
            ),
        '/dashboard': (context) => Scaffold(
              appBar: Header(
                isLoggedIn: appState.isLoggedIn,
                onLogout: _handleLogout,
                isGenerating: false,
              ),
              body: const DashboardScreen(),
            ),
        '/validity': (context) => Scaffold(
              appBar: Header(
                isLoggedIn: appState.isLoggedIn,
                onLogout: _handleLogout,
                isGenerating: false,
              ),
              body: const ValidityScreen(),
            ),
        '/knowledge-base': (context) => Scaffold(
              appBar: Header(
                isLoggedIn: appState.isLoggedIn,
                onLogout: _handleLogout,
                isGenerating: false,
              ),
              body: const KnowledgeBaseScreen(),
            ),
        '/settings': (context) => Scaffold(
              appBar: Header(
                isLoggedIn: appState.isLoggedIn,
                onLogout: _handleLogout,
                isGenerating: false,
              ),
              body: const SettingsScreen(),
            ),
      },
    );
  }
}
