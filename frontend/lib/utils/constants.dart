import 'package:flutter_dotenv/flutter_dotenv.dart';

final String apiUrl = dotenv.get('API_URL', fallback: 'http://localhost:8080');
