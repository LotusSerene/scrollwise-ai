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

Future<void> setAuthToken(String token) async {
  // No need to manually set token when using Supabase
  // Supabase handles token storage internally
}

Future<void> removeAuthToken() async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.remove('token');
}

Future<Map<String, String>> getAuthHeaders() async {
  final token = await getAuthToken();
  return {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json; charset=$utf8Charset',
  };
}

class LocalStorage {
  // Simulate localStorage using a Map
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
}

final localStorage = LocalStorage();

Future<bool> isLoggedIn() async {
  final token = await getAuthToken();
  if (token == null) return false;
  return !JwtDecoder.isExpired(token);
}
