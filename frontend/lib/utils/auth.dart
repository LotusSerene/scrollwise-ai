import 'package:shared_preferences/shared_preferences.dart';
import 'package:jwt_decoder/jwt_decoder.dart';
import 'package:supabase_flutter/supabase_flutter.dart' as supabase;
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../main.dart';
import 'constants.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import 'package:logging/logging.dart';

final _logger = Logger('Auth');

const String utf8Charset = 'UTF-8';

Future<String?> getAuthToken() async {
  try {
    // First try SharedPreferences to avoid context dependency
    final prefs = await SharedPreferences.getInstance();
    String? token = prefs.getString('access_token');

    // Only try to access AppState if we have a valid context
    if (navigatorKey.currentContext != null) {
      final appState =
          Provider.of<AppState>(navigatorKey.currentContext!, listen: false);
      // Prefer AppState token over SharedPreferences if available
      token = appState.token ?? token;
    }

    return token;
  } catch (e) {
    _logger.severe('Error in getAuthToken: $e');
    return null;
  }
}

Future<String?> getUserId() async {
  final session = supabase.Supabase.instance.client.auth.currentSession;
  return session?.user.id;
}

Future<Map<String, String>> getAuthHeaders() async {
  final token = await getAuthToken();
  final sessionId = await getSessionId();

  if (token == null) {
    _logger.warning('No auth token available');
    throw Exception('No authentication token available');
  }

  // Only validate session if token exists but might be invalid
  if (!await validateSession()) {
    _logger.warning('Session validation failed');
    await _handleInvalidSession();
    throw Exception('Invalid session');
  }

  return {
    'Authorization': 'Bearer $token',
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
    final token = await getAuthToken();
    if (token == null) return false;

    // Check both Supabase token and local session
    final sessionId = await getSessionId();
    final isTokenValid = !JwtDecoder.isExpired(token);
    final hasSession = sessionId != null;

    return isTokenValid && hasSession;
  } catch (e) {
    _logger.severe('Error checking login status: $e');
    return false;
  }
}

class LocalStorage {
  final Map<String, String> _store = {};

  String? getItem(String key) {
    return _store[key];
  }

  void setItem(String key, String value) {
    _store[key] = value;
  }

  void removeItem(String key) {
    _store.remove(key);
  }

  void clear() {
    _store.clear();
  }
}

final localStorage = LocalStorage();

// Helper method to handle sign out
Future<void> signOut() async {
  try {
    // Sign out from Supabase
    await supabase.Supabase.instance.client.auth.signOut();

    // Clear local session
    await removeSessionId();

    // Clear any other stored data
    localStorage.clear();

    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
  } catch (e) {
    _logger.severe('Error during sign out: $e');
    throw Exception('Failed to sign out');
  }
}

// Helper method to refresh session
Future<bool> refreshSession() async {
  try {
    final session = supabase.Supabase.instance.client.auth.currentSession;
    if (session == null) {
      _logger.info('No current session to refresh');
      return false;
    }

    // Add retry logic for refresh
    int retries = 3;
    while (retries > 0) {
      try {
        await supabase.Supabase.instance.client.auth.refreshSession();

        final newSession =
            supabase.Supabase.instance.client.auth.currentSession;
        if (newSession != null) {
          final appState = Provider.of<AppState>(navigatorKey.currentContext!,
              listen: false);
          appState.setToken(newSession.accessToken);

          final prefs = await SharedPreferences.getInstance();
          await prefs.setString('access_token', newSession.accessToken);

          _logger.info('Session refreshed successfully');
          return true;
        }
        break; // Exit loop if refresh completed without error
      } catch (e) {
        retries--;
        if (retries > 0) {
          _logger.warning(
              'Refresh attempt failed, retrying... ($retries attempts left)');
          await Future.delayed(const Duration(seconds: 1));
        }
      }
    }

    return false;
  } catch (e) {
    _logger.severe('Error in refreshSession: $e');
    return false;
  }
}

// Helper method to validate current session
Future<bool> validateSession() async {
  try {
    final token = await getAuthToken();
    final sessionId = await getSessionId();

    if (token == null || sessionId == null) {
      _logger.info('No token or session ID available');
      return false;
    }

    // Check if token is valid
    if (!JwtDecoder.isExpired(token)) {
      final supabaseClient = supabase.Supabase.instance.client;

      // Try to recover Supabase session if needed
      if (supabaseClient.auth.currentSession == null) {
        try {
          await supabaseClient.auth.recoverSession(token);
        } catch (e) {
          _logger.warning('Failed to recover Supabase session: $e');
          // Don't immediately fail - continue with local validation
        }
      }

      // Check if session needs extension
      final tokenExpiration = JwtDecoder.getExpirationDate(token);
      if (tokenExpiration.difference(DateTime.now()).inHours < 12) {
        // Increased from 6 to 12
        _logger.info('Token expiring soon, extending session');
        if (!await _extendSession()) {
          _logger.warning('Failed to extend session');
          // Don't immediately fail - token is still valid
        }
      }

      return true;
    }

    // Token is expired, try refresh
    _logger.info('Token expired, attempting refresh');
    return await refreshSession();
  } catch (e) {
    _logger.warning('Error in validateSession: $e');
    return false;
  }
}

Future<bool> _extendSession() async {
  try {
    final response = await http.post(
      Uri.parse('$apiUrl/auth/extend-session'),
      headers: await getAuthHeaders(),
    );
    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      // We only need to handle session ID
      if (data['session_id'] != null) {
        await setSessionId(data['session_id']);
        return true;
      }
    }
    return false;
  } catch (e) {
    _logger.severe('Error extending session: $e');
    return false;
  }
}

// Helper method to initialize session
Future<void> initializeSession(String token, String sessionId) async {
  try {
    await setSessionId(sessionId);
    await persistSupabaseSession(token);

    // Store token in AppState and SharedPreferences
    final appState =
        Provider.of<AppState>(navigatorKey.currentContext!, listen: false);
    appState.setToken(token);

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('access_token', token);
  } catch (e) {
    _logger.severe('Error initializing session: $e');
    throw Exception('Failed to initialize session');
  }
}

// Add new method to persist Supabase session
Future<void> persistSupabaseSession(String token) async {
  try {
    final supabaseClient = supabase.Supabase.instance.client;
    if (supabaseClient.auth.currentSession == null) {
      // Don't try to recover session with our custom JWT
      // Instead, just initialize a new session
      await supabaseClient.auth.setSession(token);
    }
  } catch (e) {
    _logger.warning('Could not persist Supabase session: $e');
    // Don't throw - this is not critical
  }
}

// Add this new method to handle invalid sessions
Future<void> _handleInvalidSession() async {
  try {
    // Clear all session data
    await signOut();

    // Update AppState
    final appState =
        Provider.of<AppState>(navigatorKey.currentContext!, listen: false);
    appState.setLoggedIn(false);
    appState.setToken(null);

    // Navigate to login screen
    navigatorKey.currentState
        ?.pushNamedAndRemoveUntil('/login', (route) => false);
  } catch (e) {
    _logger.severe('Error handling invalid session: $e');
  }
}

// Add this new method to initialize auth state on app start
Future<void> initializeAuthState() async {
  try {
    final token = await getAuthToken();
    if (token != null && !JwtDecoder.isExpired(token)) {
      // Skip Supabase session recovery
      if (await validateSession()) {
        // Only update AppState if we have a valid context
        if (navigatorKey.currentContext != null) {
          final appState = Provider.of<AppState>(
            navigatorKey.currentContext!,
            listen: false,
          );
          appState.setLoggedIn(true);
          appState.setToken(token);
        }
        return;
      }
    }

    await _handleInvalidSession();
  } catch (e) {
    _logger.severe('Error initializing auth state: $e');
    await _handleInvalidSession();
  }
}
