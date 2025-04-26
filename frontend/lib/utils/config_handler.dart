class ConfigHandler {
  static final Map<String, String> _config = {
    // Removed Supabase keys (already removed in provided file, ensuring consistency)
    'API_URL': const String.fromEnvironment('API_URL',
        defaultValue: 'http://localhost:8080'), // Keep API_URL
  };

  static String get(String key, {String fallback = ''}) {
    return _config[key] ?? fallback;
  }

  static Map<String, String> getEnvVars() {
    return Map<String, String>.from(_config);
  }
}
