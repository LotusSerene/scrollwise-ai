import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:logging/logging.dart';
import '../main.dart';
import '../providers/app_state.dart';
import 'package:provider/provider.dart' as provider_pkg;

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
  // final sessionId = await getSessionId(); // Removed custom session ID logic

  if (session?.accessToken == null) {
    _logger.warning('No auth token available');
    throw Exception('No authentication token available');
  }

  return {
    'Authorization': 'Bearer ${session!.accessToken}',
    // if (sessionId != null) 'X-Session-ID': sessionId, // Removed custom session ID logic
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };
}

// Removed custom session ID management functions (setSessionId, removeSessionId, getSessionId)

Future<bool> isLoggedIn() async {
  try {
    final session = Supabase.instance.client.auth.currentSession;
    // final sessionId = await getSessionId().timeout( // Removed custom session ID logic
    //   const Duration(seconds: 2),
    //   onTimeout: () {
    //     _logger.warning('getSessionId timed out');
    //     return null;
    //   },
    // );

    // Login status now depends only on Supabase session
    return session != null;
  } catch (e) {
    _logger.severe('Error checking login status: $e');
    return false;
  }
}

// Helper method to handle sign out
Future<void> signOut() async {
  try {
    // final sessionId = await getSessionId(); // Removed custom session ID logic

    // Removed backend signout attempt using custom session ID
    // try {
    //   final session = Supabase.instance.client.auth.currentSession;
    //   await http.post(
    //     Uri.parse('$apiUrl/auth/signout'), // Assuming backend signout still uses JWT
    //     headers: {
    //       if (session?.accessToken != null)
    //         'Authorization': 'Bearer ${session!.accessToken}',
    //       // 'X-Session-ID': sessionId, // Removed
    //     },
    //   ).timeout(const Duration(seconds: 5));
    // } catch (e) {
    //   _logger.warning('Backend signout failed: $e');
    // }

    // Sign out from Supabase
    await Supabase.instance.client.auth.signOut();

    // Clear local session
    // await removeSessionId(); // Removed custom session ID logic

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
    // await removeSessionId(); // Removed custom session ID logic
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
    // final sessionId = await getSessionId().timeout( // Removed custom session ID logic
    //   const Duration(seconds: 5),
    //   onTimeout: () {
    //     _logger.warning('getSessionId timed out');
    //     return null;
    //   },
    // );

    // Removed backend session validation/extension logic
    // if (session != null /* && sessionId != null */) { // Check only Supabase session
    //   try {
    //     // If backend validation is still needed, it should rely solely on the JWT
    //     // Example: Check a protected endpoint using only the Authorization header
    //     final response = await http.get(
    //       Uri.parse('$apiUrl/auth/session'), // Example endpoint
    //       headers: {
    //         'Authorization': 'Bearer ${session.accessToken}',
    //       },
    //     ).timeout(const Duration(seconds: 5));
    //
    //     if (response.statusCode != 200) {
    //       _logger.warning(
    //           'Backend JWT validation failed with status: ${response.statusCode}');
    //       await signOut(); // Sign out if backend rejects JWT
    //       return;
    //     }
    //   } catch (e) {
    //     _logger.warning('Backend JWT validation failed: $e');
    //     await signOut();
    //     return;
    //   }
    // }

    // Update AppState only if session is valid
    if (navigatorKey.currentContext != null) {
      final appState = provider_pkg.Provider.of<AppState>(
        navigatorKey.currentContext!,
        listen: false,
      );
      // Set logged-in state based only on Supabase session
      appState.setLoggedIn(session != null);
      appState.setToken(session?.accessToken);
    }
  } catch (e) {
    _logger.severe('Error initializing auth state: $e');
    await signOut();
  }
}
