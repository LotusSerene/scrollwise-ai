import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:logging/logging.dart';
import '../main.dart';
import '../providers/app_state.dart';
import 'package:provider/provider.dart' as provider_pkg;
import 'package:http/http.dart' as http;
import 'constants.dart';

final _logger = Logger('Auth');

Future<String?> getAuthToken() async {
  try {
    final session = Supabase.instance.client.auth.currentSession;
    return session?.accessToken;
  } catch (e) {
    _logger.severe('Error in getAuthToken: $e');
    return null;
  }
}

Future<String?> getUserId() async {
  return Supabase.instance.client.auth.currentUser?.id;
}

Future<Map<String, String>> getAuthHeaders() async {
  final session = Supabase.instance.client.auth.currentSession;
  final sessionId = await getSessionId();

  if (session?.accessToken == null) {
    _logger.warning('No auth token available');
    throw Exception('No authentication token available');
  }

  return {
    'Authorization': 'Bearer ${session!.accessToken}',
    if (sessionId != null) 'X-Session-ID': sessionId,
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };
}

// Session management for local server
Future<void> setSessionId(String sessionId) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString('session_id', sessionId);
}

Future<void> removeSessionId() async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.remove('session_id');
}

Future<String?> getSessionId() async {
  final prefs = await SharedPreferences.getInstance();
  return prefs.getString('session_id');
}

Future<bool> isLoggedIn() async {
  try {
    final session = Supabase.instance.client.auth.currentSession;
    final sessionId = await getSessionId().timeout(
      const Duration(seconds: 2),
      onTimeout: () {
        _logger.warning('getSessionId timed out');
        return null;
      },
    );

    return session != null && sessionId != null;
  } catch (e) {
    _logger.severe('Error checking login status: $e');
    return false;
  }
}

// Helper method to handle sign out
Future<void> signOut() async {
  try {
    final sessionId = await getSessionId();

    // Try to sign out from backend first
    if (sessionId != null) {
      try {
        final session = Supabase.instance.client.auth.currentSession;
        await http.post(
          Uri.parse('$apiUrl/auth/signout'),
          headers: {
            if (session?.accessToken != null)
              'Authorization': 'Bearer ${session!.accessToken}',
            'X-Session-ID': sessionId,
          },
        ).timeout(const Duration(seconds: 5));
      } catch (e) {
        _logger.warning('Backend signout failed: $e');
      }
    }

    // Sign out from Supabase
    await Supabase.instance.client.auth.signOut();

    // Clear local session
    await removeSessionId();

    // Update AppState if context is available
    if (navigatorKey.currentContext != null) {
      final appState = provider_pkg.Provider.of<AppState>(
        navigatorKey.currentContext!,
        listen: false,
      );
      appState.setLoggedIn(false);
      appState.setToken(null);
    }
  } catch (e) {
    _logger.severe('Error during sign out: $e');
    // Still clear local state even if remote signout fails
    await removeSessionId();
    if (navigatorKey.currentContext != null) {
      final appState = provider_pkg.Provider.of<AppState>(
        navigatorKey.currentContext!,
        listen: false,
      );
      appState.setLoggedIn(false);
      appState.setToken(null);
    }
  }
}

// Initialize auth state on app start
Future<void> initializeAuthState() async {
  try {
    final session = Supabase.instance.client.auth.currentSession;
    final sessionId = await getSessionId().timeout(
      const Duration(seconds: 5),
      onTimeout: () {
        _logger.warning('getSessionId timed out');
        return null;
      },
    );

    if (session != null) {
      // Validate session with backend
      try {
        final response = await http.post(
          Uri.parse('$apiUrl/auth/extend-session'),
          headers: {
            'Authorization': 'Bearer ${session.accessToken}',
            if (sessionId != null) 'X-Session-ID': sessionId,
          },
        );

        if (response.statusCode != 200) {
          throw Exception('Failed to validate session');
        }
      } catch (e) {
        _logger.warning('Session validation failed: $e');
        await signOut();
        return;
      }

      // Update AppState only if session is valid
      if (navigatorKey.currentContext != null) {
        final appState = provider_pkg.Provider.of<AppState>(
          navigatorKey.currentContext!,
          listen: false,
        );
        appState.setLoggedIn(true);
        appState.setToken(session.accessToken);
      }
      return;
    }

    // Handle not logged in state
    await signOut();
  } catch (e) {
    _logger.severe('Error initializing auth state: $e');
    await signOut();
  }
}
