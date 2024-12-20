class ConfigHandler {
  static final Map<String, String> _config = {
    'SUPABASE_URL': _obfuscate(const String.fromEnvironment('SUPABASE_URL')),
    'SUPABASE_SERVICE_KEY':
        _obfuscate(const String.fromEnvironment('SUPABASE_SERVICE_KEY')),
    'SUPABASE_ANON_KEY':
        _obfuscate(const String.fromEnvironment('SUPABASE_ANON_KEY')),
    'DATABASE_URL': _obfuscate(const String.fromEnvironment('DATABASE_URL')),
    'API_URL': const String.fromEnvironment('API_URL',
        defaultValue: 'http://localhost:8080'),
  };

  // Simple obfuscation
  static String _obfuscate(String value) {
    // Add your custom obfuscation logic
    return value
        .split('')
        .map((char) => String.fromCharCode(char.codeUnitAt(0) ^ 42))
        .join('');
  }

  static String _deobfuscate(String value) {
    // Reverse the obfuscation
    return value
        .split('')
        .map((char) => String.fromCharCode(char.codeUnitAt(0) ^ 42))
        .join('');
  }

  static String get(String key, {String fallback = ''}) {
    final value = _config[key] ?? fallback;
    return key == 'API_URL' ? value : _deobfuscate(value);
  }

  // Add method to get all config as environment variables
  static Map<String, String> getEnvVars() {
    return Map<String, String>.from(_config);
  }
}
