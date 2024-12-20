import '../main.dart';

class DeepLinkHandler {
  static Future<void> handleLink(String link) async {
    final uri = Uri.parse(link);
    if (uri.path.contains('verify')) {
      navigatorKey.currentState
          ?.pushNamed('/login', arguments: uri.queryParameters['token']);
    }
  }
}
