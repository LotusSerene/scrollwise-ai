import 'package:shared_preferences/shared_preferences.dart';
import 'package:jwt_decoder/jwt_decoder.dart';
import 'package:supabase_flutter/supabase_flutter.dart' as supabase;
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../main.dart';
import 'constants.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';

const String utf8Charset = 'UTF-8';

Future<String?> getAuthToken() async {
  try {
    // First try to get from AppState
    final appState =
        Provider.of<AppState>(navigatorKey.currentContext!, listen: false);
    if (appState.token != null) {
      return appState.token;
    }

    // If not in AppState, try SharedPreferences
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');

    if (token != null) {
      // If found in SharedPreferences, update AppState
      appState.setToken(token);
    }

    return token;
  } catch (e) {
    print('Error getting auth token: $e');
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
    await _handleInvalidSession();
    throw Exception('No authentication token available');
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
    print('Error checking login status: $e');
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
    print('Error during sign out: $e');
    throw Exception('Failed to sign out');
  }
}

// Helper method to refresh session
Future<bool> refreshSession() async {
  try {
    final session = supabase.Supabase.instance.client.auth.currentSession;
    if (session == null) return false;

    // Always try to refresh the session on app restart
    await supabase.Supabase.instance.client.auth.refreshSession();

    // Get new session
    final newSession = supabase.Supabase.instance.client.auth.currentSession;
    if (newSession != null) {
      // Update the stored token with the new one
      final appState =
          Provider.of<AppState>(navigatorKey.currentContext!, listen: false);
      appState.setToken(newSession.accessToken);

      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('access_token', newSession.accessToken);

      return true;
    }
    return false;
  } catch (e) {
    print('Error refreshing session: $e');
    return false;
  }
}

// Helper method to validate current session
Future<bool> validateSession() async {
  try {
    final token = await getAuthToken();
    final sessionId = await getSessionId();

    if (token == null || sessionId == null) {
      await _handleInvalidSession();
      return false;
    }

    // Check if token is still valid
    if (!JwtDecoder.isExpired(token)) {
      // Token is still valid, try to restore Supabase session
      final supabaseClient = supabase.Supabase.instance.client;
      if (supabaseClient.auth.currentSession == null) {
        try {
          // First try to recover the session
          await supabaseClient.auth.recoverSession(token);
        } catch (e) {
          print('Error recovering Supabase session: $e');
          // If recovery fails, try to refresh
          final refreshResult = await refreshSession();
          if (!refreshResult) {
            await _handleInvalidSession();
            return false;
          }
        }
      }

      // Check if local session needs extension
      final tokenExpiration = JwtDecoder.getExpirationDate(token);
      if (tokenExpiration.difference(DateTime.now()).inHours < 6) {
        final extendResult = await _extendSession();
        if (!extendResult) {
          await _handleInvalidSession();
          return false;
        }
      }
      return true;
    }

    // If token is expired, try refresh
    final refreshResult = await refreshSession();
    if (!refreshResult) {
      await _handleInvalidSession();
      return false;
    }
    return true;
  } catch (e) {
    print('Error validating session: $e');
    await _handleInvalidSession();
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
    print('Error extending session: $e');
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
    print('Error initializing session: $e');
    throw Exception('Failed to initialize session');
  }
}

// Add new method to persist Supabase session
Future<void> persistSupabaseSession(String token) async {
  try {
    final supabaseClient = supabase.Supabase.instance.client;
    if (supabaseClient.auth.currentSession == null) {
      await supabaseClient.auth.recoverSession(token);
    }
  } catch (e) {
    print('Error persisting Supabase session: $e');
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
    print('Error handling invalid session: $e');
  }
}

// Add this new method to initialize auth state on app start
Future<void> initializeAuthState() async {
  try {
    final token = await getAuthToken();
    if (token != null && !JwtDecoder.isExpired(token)) {
      final supabaseClient = supabase.Supabase.instance.client;

      // Try to recover session first
      try {
        await supabaseClient.auth.recoverSession(token);

        // Verify the session is valid
        if (await validateSession()) {
          // Update AppState
          final appState = Provider.of<AppState>(navigatorKey.currentContext!,
              listen: false);
          appState.setLoggedIn(true);
          appState.setToken(token);
          return;
        }
      } catch (e) {
        print('Error recovering session: $e');
      }
    }

    // If we get here, either there was no token or it was invalid
    await _handleInvalidSession();
  } catch (e) {
    print('Error initializing auth state: $e');
    await _handleInvalidSession();
  }
}
