// Removed Supabase imports and other unused imports
import 'package:logging/logging.dart';
// Removed main.dart import (navigatorKey not needed here anymore)
// Removed AppState import
// Removed provider import

final _logger = Logger('Auth'); // Keep logger if needed for header errors

// Removed getAuthToken
// Removed getUserId

// Simplified header function - no auth needed for local app
Future<Map<String, String>> getAuthHeaders() async {
  // No token or session needed
  return {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };
}

// Removed isLoggedIn
// Removed signOut
// Removed initializeAuthState
