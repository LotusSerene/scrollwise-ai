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
      return false;
    }

    // First try to refresh the Supabase session
    final refreshResult = await refreshSession();
    if (!refreshResult) {
      return false;
    }

    // Then check if we need to extend the local session
    if (JwtDecoder.isExpired(token) ||
        JwtDecoder.getExpirationDate(token).difference(DateTime.now()).inHours <
            6) {
      // Attempt to extend session
      final extendResult = await _extendSession();
      if (!extendResult) {
        return false;
      }
    }
    return true;
  } catch (e) {
    print('Error validating session: $e');
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
  } catch (e) {
    print('Error initializing session: $e');
    throw Exception('Failed to initialize session');
  }
}
