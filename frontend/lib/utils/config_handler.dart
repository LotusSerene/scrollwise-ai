class ConfigHandler {
  static final Map<String, String> _config = {
    'SUPABASE_URL': const String.fromEnvironment('SUPABASE_URL'),
    'SUPABASE_SERVICE_KEY':
        const String.fromEnvironment('SUPABASE_SERVICE_KEY'),
    'SUPABASE_ANON_KEY': const String.fromEnvironment('SUPABASE_ANON_KEY'),
    'API_URL': const String.fromEnvironment('API_URL',
        defaultValue: 'http://localhost:8080'),
  };

  static String get(String key, {String fallback = ''}) {
    return _config[key] ?? fallback;
  }

  static Map<String, String> getEnvVars() {
    return Map<String, String>.from(_config);
  }
}
