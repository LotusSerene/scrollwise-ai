import 'config_handler.dart';

final String apiUrl =
    ConfigHandler.get('API_URL', fallback: 'http://localhost:8080');
