import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:provider/provider.dart';
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
import 'screens/chapters_screen.dart'; // Import ChaptersScreen
import 'utils/auth.dart';
import 'utils/theme.dart';
import 'package:flutter/services.dart';
import 'providers/preset_provider.dart';
import 'providers/relationship_provider.dart';
import 'screens/timeline_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load();

  // Increase the buffer size for the lifecycle channel
  SystemChannels.lifecycle.setMessageHandler((message) async {
    return null;
  });

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
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Gemini Frontend',
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.dark,
      initialRoute: '/',
      routes: {
        '/': (context) => const AuthWrapper(),
        '/projects': (context) => const ProjectsScreen(),
        '/home': (context) => const HomeScreen(),
        '/login': (context) => LoginScreen(onLogin: (token) {
              Provider.of<AppState>(context, listen: false).setLoggedIn(true);
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
          return LoginScreen(onLogin: (token) {
            Provider.of<AppState>(context, listen: false).setLoggedIn(true);
            Navigator.pushReplacementNamed(context, '/projects');
          });
        }
      },
    );
  }
}
