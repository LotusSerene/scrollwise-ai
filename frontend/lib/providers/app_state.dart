import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';

class AppState extends ChangeNotifier {
  bool _isLoggedIn = false;
  String? _currentProjectId;
  List<dynamic> _chapters = [];
  List<dynamic> _codexItems = [];
  List<dynamic> _validityChecks = [];
  String? _token;
  int _chaptersRead = 0;
  int _codexEntries = 0;
  int _wordCount = 0;
  int _targetWordCount = 0;

  bool get isLoggedIn => _isLoggedIn;
  String? get currentProjectId => _currentProjectId;
  List<dynamic> get chapters => _chapters;
  List<dynamic> get codexItems => _codexItems;
  List<dynamic> get validityChecks => _validityChecks;
  String? get token => _token;

  int get chaptersRead => _chaptersRead;
  int get codexEntries => _codexEntries;
  int get wordCount => _wordCount;
  int get targetWordCount => _targetWordCount;

  void setLoggedIn(bool value) {
    _isLoggedIn = value;
    notifyListeners();
  }

  Future<void> setCurrentProject(String? projectId) async {
    _currentProjectId = projectId;
    // Clear existing data when switching projects
    _chapters = [];
    _codexItems = [];
    _validityChecks = [];
    _chaptersRead = 0;
    _codexEntries = 0;
    _wordCount = 0;
    _targetWordCount = 0; // Reset progress when switching projects
    notifyListeners();

    if (projectId != null) {
      await fetchProgressData(projectId);
    }
  }

  void setToken(String? token) {
    _token = token;
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

  void updateProgress(int chaptersRead, int codexEntries, int wordCount) {
    _chaptersRead = chaptersRead;
    _codexEntries = codexEntries;
    _wordCount = wordCount;
    notifyListeners();
  }

  Future<void> updateTargetWordCount(int targetWordCount) async {
    _targetWordCount = targetWordCount;
    notifyListeners();

    if (_currentProjectId != null) {
      try {
        final headers = await getAuthHeaders();
        headers['Content-Type'] = 'application/json';
        final response = await http.put(
          Uri.parse('$apiUrl/projects/$_currentProjectId'),
          headers: headers,
          body: json.encode({'target_word_count': targetWordCount}),
        );

        if (response.statusCode != 200) {}
      } catch (error) {}
    }
  }

  Future<void> fetchProgressData(String projectId) async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/projects/$projectId'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final projectData = json.decode(utf8.decode(response.bodyBytes));
        // Assuming the backend stores progress data in the project object
        _chaptersRead = projectData['chaptersRead'] ?? 0;
        _codexEntries = projectData['codexEntries'] ?? 0;
        _wordCount = projectData['wordCount'] ?? 0;
        _targetWordCount = projectData['targetWordCount'] ?? 0;
        notifyListeners();
      } else {
        // Handle error fetching progress data
        print('Error fetching progress data: ${response.statusCode}');
      }
    } catch (error) {
      // Handle error fetching progress data
      print('Error fetching progress data: $error');
    }
  }

  Future<void> _updateTargetWordCountInBackend(
      String projectId, int targetWordCount) async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.put(
        Uri.parse('$apiUrl/projects/$projectId'),
        headers: headers,
        body: json.encode({'targetWordCount': targetWordCount}),
      );

      if (response.statusCode != 200) {
        // Handle error updating target word count
        print('Error updating target word count: ${response.statusCode}');
      }
    } catch (error) {
      // Handle error updating target word count
      print('Error updating target word count: $error');
    }
  }

  Future<void> refreshProjectData() async {
    if (_currentProjectId != null) {
      await fetchProgressData(_currentProjectId!);
      await fetchChapters(_currentProjectId!);
      await fetchCodexItems(_currentProjectId!);
    }
  }

  Future<void> fetchChapters(String projectId) async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/chapters?project_id=$projectId'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(utf8.decode(response.bodyBytes));
        setChapters(data['chapters']);
      } else {
        print('Error fetching chapters: ${response.statusCode}');
      }
    } catch (error) {
      print('Error fetching chapters: $error');
    }
  }

  Future<void> fetchCodexItems(String projectId) async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/codex-items?project_id=$projectId'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(utf8.decode(response.bodyBytes));
        setCodexItems(data['codex_items']);
      } else {
        print('Error fetching codex items: ${response.statusCode}');
      }
    } catch (error) {
      print('Error fetching codex items: $error');
    }
  }
}
