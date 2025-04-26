import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart'; // Keep constants
import 'package:logging/logging.dart';
// Removed Supabase import

final _logger = Logger('AppState');

class GenerationState {
  final String type;
  final String? subtype;
  final String? description;
  final bool isGenerating;
  final dynamic lastGeneratedItem;

  GenerationState({
    required this.type,
    this.subtype,
    this.description,
    this.isGenerating = false,
    this.lastGeneratedItem,
  });
}

class AppState extends ChangeNotifier {
  // Removed _isLoggedIn
  String? _currentProjectId;
  List<dynamic> _chapters = [];
  List<dynamic> _codexItems = [];
  List<dynamic> _validityChecks = [];
  // Removed _token
  int _chaptersRead = 0;
  int _codexEntries = 0;
  int _wordCount = 0;
  int _targetWordCount = 0;

  // Removed isLoggedIn getter
  String? get currentProjectId => _currentProjectId;
  List<dynamic> get chapters => _chapters;
  List<dynamic> get codexItems => _codexItems;
  List<dynamic> get validityChecks => _validityChecks;
  // Removed token getter

  int get chaptersRead => _chaptersRead;
  int get codexEntries => _codexEntries;
  int get wordCount => _wordCount;
  int get targetWordCount => _targetWordCount;

  final Map<String, GenerationState> _generationStates = {
    'chapter': GenerationState(type: 'chapter'),
    'codex': GenerationState(type: 'codex'),
    'timeline': GenerationState(type: 'timeline'),
    'character_journey': GenerationState(type: 'character_journey'),
    'character_relationships': GenerationState(type: 'character_relationships'),
  };

  // Removed checkAuthState
  // Removed setLoggedIn
  // Removed setToken

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

        if (response.statusCode != 200) {
          _logger.severe(
              'Error updating target word count: ${response.statusCode}');
        }
      } catch (error) {
        _logger.severe('Error updating target word count: $error');
      }
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
        _logger.severe('Error fetching progress data: ${response.statusCode}');
      }
    } catch (error) {
      // Handle error fetching progress data
      _logger.severe('Error fetching progress data: $error');
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
        Uri.parse('$apiUrl/projects/$projectId/chapters/'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(utf8.decode(response.bodyBytes));
        final chapters = data['chapters'];
        if (chapters == null) {
          throw Exception('Invalid response format: missing chapters key');
        }
        setChapters(chapters);
      } else {
        throw Exception('Failed to fetch chapters: ${response.statusCode}');
      }
    } catch (error) {
      _logger.severe('Error fetching chapters: $error');
      // Rethrow to allow UI to handle the error
      rethrow;
    }
  }

  Future<void> fetchCodexItems(String projectId) async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/projects/$projectId/codex-items/'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(utf8.decode(response.bodyBytes));
        final items = data['codex_items'];
        if (items == null) {
          throw Exception('Invalid response format: missing codex_items key');
        }
        setCodexItems(items);
      } else {
        throw Exception('Failed to fetch codex items: ${response.statusCode}');
      }
    } catch (error) {
      _logger.severe('Error fetching codex items: $error');
      rethrow;
    }
  }

  Future<void> fetchValidityChecks(String projectId) async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/projects/$projectId/validity-checks/'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(utf8.decode(response.bodyBytes));
        final checks = data['validity_checks'];
        if (checks == null) {
          throw Exception(
              'Invalid response format: missing validity_checks key');
        }
        setValidityChecks(checks);
      } else {
        throw Exception(
            'Failed to fetch validity checks: ${response.statusCode}');
      }
    } catch (error) {
      _logger.severe('Error fetching validity checks: $error');
      rethrow;
    }
  }

  void setGenerationState(
    String type, {
    String? subtype,
    String? description,
    bool? isGenerating,
    dynamic lastGeneratedItem,
  }) {
    final currentState = _generationStates[type];
    if (currentState != null) {
      _generationStates[type] = GenerationState(
        type: type,
        subtype: subtype ?? currentState.subtype,
        description: description ?? currentState.description,
        isGenerating: isGenerating ?? currentState.isGenerating,
        lastGeneratedItem: lastGeneratedItem ?? currentState.lastGeneratedItem,
      );
      notifyListeners();
    }
  }

  void resetGenerationState(String type) {
    _generationStates[type] = GenerationState(type: type);
    notifyListeners();
  }

  void resetAllGenerationStates() {
    for (var type in _generationStates.keys) {
      _generationStates[type] = GenerationState(type: type);
    }
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
    _targetWordCount = 0;
    resetAllGenerationStates();
    resetChapterCreationState();
    resetCodexGenerationState();
    resetCharacterRelationshipsState();
    resetCharacterJourneyState();
    resetTimelineState();
    resetQueryState();
    notifyListeners();

    if (projectId != null) {
      await fetchProgressData(projectId);
    }
  }

  // Add new fields for chapter creation
  Map<String, dynamic> _chapterCreationState = {
    'numChapters': 1,
    'plot': '',
    'writingStyle': '',
    'styleGuide': '',
    'wordCount': '1000',
    'additionalInstructions': '',
    'isGenerating': false,
    'currentChapter': 0,
    'progress': 0.0,
    'streamedContent': '',
    'generatedChapters': <String>[],
  };

  Map<String, dynamic> get chapterCreationState => _chapterCreationState;

  void updateChapterCreationField(String field, dynamic value) {
    _chapterCreationState[field] = value;
    notifyListeners();
  }

  void resetChapterCreationState() {
    _chapterCreationState = {
      'numChapters': 1,
      'plot': '',
      'writingStyle': '',
      'styleGuide': '',
      'wordCount': '1000',
      'additionalInstructions': '',
      'isGenerating': false,
      'currentChapter': 0,
      'progress': 0.0,
      'streamedContent': '',
      'generatedChapters': <String>[],
    };
    notifyListeners();
  }

  void updateGenerationProgress({
    bool? isGenerating,
    int? currentChapter,
    double? progress,
    String? streamedContent,
    List<String>? generatedChapters,
  }) {
    if (isGenerating != null) {
      _chapterCreationState['isGenerating'] = isGenerating;
    }
    if (currentChapter != null) {
      _chapterCreationState['currentChapter'] = currentChapter;
    }
    if (progress != null) _chapterCreationState['progress'] = progress;
    if (streamedContent != null) {
      _chapterCreationState['streamedContent'] = streamedContent;
    }
    if (generatedChapters != null) {
      _chapterCreationState['generatedChapters'] = generatedChapters;
    } else if (!_chapterCreationState.containsKey('generatedChapters')) {
      // Initialize with empty list if not present
      _chapterCreationState['generatedChapters'] = <String>[];
    }
    notifyListeners();
  }

  void completeChapterGeneration() {
    // Called when generation completes successfully
    updateGenerationProgress(
      isGenerating: false,
      progress: 1.0,
    );

    // Optionally clear other fields while keeping the generated chapters
    _chapterCreationState['plot'] = '';
    _chapterCreationState['writingStyle'] = '';
    _chapterCreationState['styleGuide'] = '';
    _chapterCreationState['wordCount'] = '1000';
    _chapterCreationState['additionalInstructions'] = '';
    _chapterCreationState['currentChapter'] = 0;
    _chapterCreationState['streamedContent'] = '';

    notifyListeners();
  }

  void cancelChapterGeneration() {
    // Called when generation is cancelled
    updateGenerationProgress(
      isGenerating: false,
      progress: 0.0,
      currentChapter: 0,
      streamedContent: '',
    );
    notifyListeners();
  }

  // Add codex generation state
  Map<String, dynamic> _codexGenerationState = {
    'type': 'worldbuilding',
    'subtype': null,
    'description': '',
    'isGenerating': false,
    'generatedItem': null,
  };

  Map<String, dynamic> get codexGenerationState => _codexGenerationState;

  void updateCodexGenerationField(String field, dynamic value) {
    _codexGenerationState[field] = value;
    notifyListeners();
  }

  void resetCodexGenerationState() {
    _codexGenerationState = {
      'type': 'worldbuilding',
      'subtype': null,
      'description': '',
      'isGenerating': false,
      'generatedItem': null,
    };
    notifyListeners();
  }

  void updateCodexGenerationProgress({
    bool? isGenerating,
    dynamic generatedItem,
  }) {
    if (isGenerating != null) {
      _codexGenerationState['isGenerating'] = isGenerating;
    }
    if (generatedItem != null) {
      _codexGenerationState['generatedItem'] = generatedItem;
    }
    notifyListeners();
  }

  // Add character relationships state
  Map<String, dynamic> _characterRelationshipsState = {
    'selectedCharacters': <String>{},
    'isGenerating': false,
    'lastAnalyzedCharacters': null,
  };

  Map<String, dynamic> get characterRelationshipsState =>
      _characterRelationshipsState;

  void resetCharacterRelationshipsState() {
    _characterRelationshipsState = {
      'selectedCharacters': <String>{},
      'isGenerating': false,
      'lastAnalyzedCharacters': null,
    };
    notifyListeners();
  }

  void updateCharacterRelationshipsProgress({
    bool? isGenerating,
    Set<String>? selectedCharacters,
    dynamic lastAnalyzedCharacters,
  }) {
    if (isGenerating != null) {
      _characterRelationshipsState['isGenerating'] = isGenerating;
    }
    if (selectedCharacters != null) {
      _characterRelationshipsState['selectedCharacters'] = selectedCharacters;
    }
    if (lastAnalyzedCharacters != null) {
      _characterRelationshipsState['lastAnalyzedCharacters'] =
          lastAnalyzedCharacters;
    }
    notifyListeners();
  }

  // Add character journey state
  Map<String, dynamic> _characterJourneyState = {
    'ignoredCharacters': <String>{},
    'isGenerating': false,
    'lastGeneratedItem': null,
  };

  Map<String, dynamic> get characterJourneyState => _characterJourneyState;

  void updateCharacterJourneyField(String field, dynamic value) {
    _characterJourneyState[field] = value;
    notifyListeners();
  }

  void resetCharacterJourneyState() {
    _characterJourneyState = {
      'ignoredCharacters': <String>{},
      'isGenerating': false,
      'lastGeneratedItem': null,
    };
    notifyListeners();
  }

  void updateCharacterJourneyProgress({
    bool? isGenerating,
    Set<String>? ignoredCharacters,
    dynamic lastGeneratedItem,
  }) {
    if (isGenerating != null) {
      _characterJourneyState['isGenerating'] = isGenerating;
    }
    if (ignoredCharacters != null) {
      _characterJourneyState['ignoredCharacters'] = ignoredCharacters;
    }
    if (lastGeneratedItem != null) {
      _characterJourneyState['lastGeneratedItem'] = lastGeneratedItem;
    }
    notifyListeners();
  }

  // Add timeline state
  Map<String, dynamic> _timelineState = {
    'isGenerating': false,
    'lastGeneratedItem': null,
    'isAlreadyAnalyzed': false,
    'activeTab': 0,
  };

  Map<String, dynamic> get timelineState => _timelineState;

  void updateTimelineField(String field, dynamic value) {
    _timelineState[field] = value;
    notifyListeners();
  }

  void resetTimelineState() {
    _timelineState = {
      'isGenerating': false,
      'lastGeneratedItem': null,
      'isAlreadyAnalyzed': false,
      'activeTab': 0,
    };
    notifyListeners();
  }

  void updateTimelineProgress({
    bool? isGenerating,
    dynamic lastGeneratedItem,
    bool? isAlreadyAnalyzed,
    int? activeTab,
  }) {
    if (isGenerating != null) _timelineState['isGenerating'] = isGenerating;
    if (lastGeneratedItem != null) {
      _timelineState['lastGeneratedItem'] = lastGeneratedItem;
    }
    if (isAlreadyAnalyzed != null) {
      _timelineState['isAlreadyAnalyzed'] = isAlreadyAnalyzed;
    }
    if (activeTab != null) _timelineState['activeTab'] = activeTab;
    notifyListeners();
  }

  // Add query state
  Map<String, dynamic> _queryState = {
    'chatHistory': <Map<String, dynamic>>[],
    'isLoading': false,
    'lastQuery': null,
  };

  Map<String, dynamic> get queryState => _queryState;

  void updateQueryField(String field, dynamic value) {
    _queryState[field] = value;
    notifyListeners();
  }

  void resetQueryState() {
    _queryState = {
      'chatHistory': <Map<String, dynamic>>[],
      'isLoading': false,
      'lastQuery': null,
    };
    notifyListeners();
  }

  void updateQueryProgress({
    List<Map<String, dynamic>>? chatHistory,
    bool? isLoading,
    String? lastQuery,
  }) {
    if (chatHistory != null) _queryState['chatHistory'] = chatHistory;
    if (isLoading != null) _queryState['isLoading'] = isLoading;
    if (lastQuery != null) _queryState['lastQuery'] = lastQuery;
    notifyListeners();
  }
}
