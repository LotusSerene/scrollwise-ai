import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/constants.dart';

import 'package:logging/logging.dart';

final _logger = Logger('PresetProvider');

class PresetProvider with ChangeNotifier {
  List<String> _presets = [];
  String? _selectedPreset;
  Map<String, dynamic>? _currentPreset;
  bool _isLoading = false;
  String? _currentProjectId;

  List<String> get presets => _presets;
  String? get selectedPreset => _selectedPreset;
  Map<String, dynamic>? get currentPreset => _currentPreset;
  bool get isLoading => _isLoading;

  void setProjectId(String projectId) {
    _currentProjectId = projectId;
  }

  Future<void> fetchPresets() async {
    if (_currentProjectId == null) {
      throw Exception('No project ID set');
    }

    _isLoading = true;
    notifyListeners();

    try {
      final response = await http.get(
        Uri.parse('$apiUrl/projects/$_currentProjectId/presets'),
      );

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        final List<dynamic> presetList = data['presets'];
        _presets =
            presetList.map((preset) => preset['name'] as String).toList();
        notifyListeners();
      } else {
        throw Exception('Failed to load presets: ${response.statusCode}');
      }
    } catch (error) {
      _logger.severe('Error fetching presets: $error');
      rethrow;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> loadPreset(String presetName) async {
    if (presetName == "select a preset") {
      _selectedPreset = null;
      _currentPreset = null;
      notifyListeners();
      return;
    }
    try {
      final response = await http.get(
        Uri.parse(
            '$apiUrl/projects/$_currentProjectId/presets/${Uri.encodeComponent(presetName)}'),
      );

      if (response.statusCode == 200) {
        final preset = json.decode(response.body);
        _selectedPreset = presetName;
        _currentPreset = preset['data'];
        notifyListeners();
      } else {
        throw Exception('Failed to load preset: ${response.statusCode}');
      }
    } catch (error) {
      _logger.severe('Error loading preset: $error');
      rethrow;
    }
  }

  Future<void> savePreset(
      String presetName, Map<String, dynamic> presetData) async {
    try {
      if (_currentProjectId == null) {
        throw Exception('No project ID set');
      }

      final response = await http.post(
        Uri.parse('$apiUrl/projects/$_currentProjectId/presets'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: json.encode({
          'name': presetName,
          'data': presetData,
          'project_id': _currentProjectId,
        }),
      );

      if (response.statusCode == 200) {
        await fetchPresets();
      } else {
        throw Exception(
            'Failed to save preset: ${response.statusCode} - ${response.body}');
      }
    } catch (error) {
      _logger.severe('Error saving preset: $error');
      rethrow;
    }
  }

  Future<void> deletePreset(String presetName) async {
    try {
      if (_currentProjectId == null) {
        throw Exception('No project ID set');
      }

      final response = await http.delete(
        Uri.parse(
            '$apiUrl/projects/$_currentProjectId/presets/${Uri.encodeComponent(presetName)}'),
      );

      if (response.statusCode == 200) {
        _presets.remove(presetName);
        if (_selectedPreset == presetName) {
          _selectedPreset = null;
          _currentPreset = null;
        }
        await fetchPresets(); // Refresh the list after deletion
        notifyListeners();
      } else {
        throw Exception(
            'Failed to delete preset: ${response.statusCode} - ${response.body}');
      }
    } catch (error) {
      _logger.severe('Error deleting preset: $error');
      rethrow;
    }
  }

  Map<String, dynamic> get defaultPreset => {
        'numChapters': 1,
        'plot': '',
        'writingStyle': '',
        'styleGuide': '',
        'wordCount': 1000,
        'additionalInstructions': '',
      };
}
