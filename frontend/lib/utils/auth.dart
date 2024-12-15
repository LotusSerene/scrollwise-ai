// flutterfrontend/lib/utils/auth.dart

import 'package:shared_preferences/shared_preferences.dart';
import 'package:jwt_decoder/jwt_decoder.dart';
import 'package:supabase_flutter/supabase_flutter.dart' as supabase;

const String utf8Charset = 'UTF-8';

Future<String?> getAuthToken() async {
  final session = supabase.Supabase.instance.client.auth.currentSession;
  return session?.accessToken;
}

Future<String?> getUserId() async {
  final session = supabase.Supabase.instance.client.auth.currentSession;
  return session?.user.id;
}

Future<Map<String, String>> getAuthHeaders() async {
  final token = await getAuthToken();
  final sessionId = await getSessionId();
  return {
    'Authorization': 'Bearer $token',
    if (sessionId != null) 'X-Session-ID': sessionId,
    'Content-Type': 'application/json',
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

    // Check if token needs refresh
    if (session.accessToken.isEmpty ||
        JwtDecoder.isExpired(session.accessToken)) {
      // Attempt to refresh the session
      await supabase.Supabase.instance.client.auth.refreshSession();

      // Get new session
      final newSession = supabase.Supabase.instance.client.auth.currentSession;
      return newSession != null &&
          !JwtDecoder.isExpired(newSession.accessToken);
    }

    return true;
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

    // Check if token is expired
    if (JwtDecoder.isExpired(token)) {
      // Attempt to refresh session
      return await refreshSession();
    }

    return true;
  } catch (e) {
    print('Error validating session: $e');
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
