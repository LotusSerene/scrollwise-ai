import 'package:flutter/foundation.dart';

class AppState extends ChangeNotifier {
  bool _isLoggedIn = false;
  List<dynamic> _chapters = [];

  bool get isLoggedIn => _isLoggedIn;
  List<dynamic> get chapters => _chapters;

  void setLoggedIn(bool value) {
    _isLoggedIn = value;
    notifyListeners();
  }

  void addChapter(dynamic chapter) {
    _chapters.add(chapter);
    notifyListeners();
  }

  void setChapters(List<dynamic> chapters) {
    _chapters = chapters;
    notifyListeners();
  }
}
