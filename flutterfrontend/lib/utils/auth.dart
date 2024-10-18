// flutterfrontend/lib/utils/auth.dart

import 'package:shared_preferences/shared_preferences.dart';
import 'package:jwt_decoder/jwt_decoder.dart';

Future<String?> getAuthToken() async {
  final prefs = await SharedPreferences.getInstance();
  return prefs.getString('token');
}

Future<String?> getUserId() async {
  final token = await getAuthToken();
  if (token != null) {
    final decodedToken = JwtDecoder.decode(token);
    return decodedToken['sub'];
  }
  return null;
}

Future<void> setAuthToken(String token) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString('token', token);
}

Future<void> removeAuthToken() async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.remove('token');
}

Future<Map<String, String>> getAuthHeaders() async {
  final token = await getAuthToken();
  return {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
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
