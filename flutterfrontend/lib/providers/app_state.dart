import 'package:flutter/foundation.dart';

class AppState extends ChangeNotifier {
  bool _isLoggedIn = false;
  List<dynamic> _chapters = [];
  List<dynamic> _codexItems = [];
  List<dynamic> _validityChecks = [];

  bool get isLoggedIn => _isLoggedIn;
  List<dynamic> get chapters => _chapters;
  List<dynamic> get codexItems => _codexItems;
  List<dynamic> get validityChecks => _validityChecks;

  void setLoggedIn(bool value) {
    _isLoggedIn = value;
    notifyListeners();
  }

  void setChapters(List<dynamic> chapters) {
    _chapters = chapters;
    notifyListeners();
  }

  void addChapter(dynamic chapter) {
    _chapters.add(chapter);
    notifyListeners();
  }

  void updateChapter(dynamic updatedChapter) {
    final index = _chapters
        .indexWhere((chapter) => chapter['id'] == updatedChapter['id']);
    if (index != -1) {
      _chapters[index] = updatedChapter;
      notifyListeners();
    }
  }

  void removeChapter(String chapterId) {
    _chapters.removeWhere((chapter) => chapter['id'] == chapterId);
    notifyListeners();
  }

  void setCodexItems(List<dynamic> items) {
    _codexItems = items;
    notifyListeners();
  }

  void addCodexItem(dynamic item) {
    _codexItems.add(item);
    notifyListeners();
  }

  void removeCodexItem(String itemId) {
    _codexItems.removeWhere((item) => item['id'] == itemId);
    notifyListeners();
  }

  void setValidityChecks(List<dynamic> checks) {
    _validityChecks = checks;
    notifyListeners();
  }

  void addValidityCheck(dynamic check) {
    _validityChecks.add(check);
    notifyListeners();
  }

  void removeValidityCheck(String checkId) {
    _validityChecks.removeWhere((check) => check['id'] == checkId);
    notifyListeners();
  }
}
