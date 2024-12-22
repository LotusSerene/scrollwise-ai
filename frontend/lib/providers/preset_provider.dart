import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/constants.dart';
import '../utils/auth.dart';

class PresetProvider with ChangeNotifier {
  List<String> _presets = [];
  String? _selectedPreset;
  Map<String, dynamic>? _currentPreset;
  bool _isLoading = false;

  List<String> get presets => _presets;
  String? get selectedPreset => _selectedPreset;
  Map<String, dynamic>? get currentPreset => _currentPreset;
  bool get isLoading => _isLoading;

  Future<void> fetchPresets(String projectId) async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await http.get(
        Uri.parse('$apiUrl/presets?project_id=$projectId'),
        headers: await getAuthHeaders(),
      );

      if (response.statusCode == 200) {
        final List<dynamic> presetList = json.decode(response.body);
        _presets =
            presetList.map((preset) => preset['name'] as String).toList();
      } else {
        throw Exception('Failed to load presets');
      }
    } catch (error) {
      print('Error fetching presets: $error');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> loadPreset(String presetName, String projectId) async {
    if (presetName == "select a preset") {
      _selectedPreset = null;
      _currentPreset = null;
      notifyListeners();
      return;
    }
    try {
      final response = await http.get(
        Uri.parse(
            '$apiUrl/presets/${Uri.encodeComponent(presetName)}?project_id=$projectId'),
        headers: await getAuthHeaders(),
      );

      if (response.statusCode == 200) {
        final preset = json.decode(response.body);
        _selectedPreset = presetName;
        _currentPreset = preset['data'];
        notifyListeners();
      } else {
        throw Exception('Failed to load preset');
      }
    } catch (error) {
      print('Error fetching preset: $error');
      rethrow;
    }
  }

  void clearSelectedPreset() {
    _selectedPreset = null;
    _currentPreset = {
      'numChapters': 1,
      'plot': '',
      'writingStyle': '',
      'styleGuide': '',
      'minWordCount': 1000,
      'additionalInstructions': '',
    };
    notifyListeners();
  }

  Future<void> savePreset(String presetName, Map<String, dynamic> presetData,
      String projectId) async {
    try {
      final response = await http.post(
        Uri.parse('$apiUrl/presets?project_id=$projectId'),
        headers: {
          ...await getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: json.encode({
          'name': presetName,
          'data': presetData,
        }),
      );

      if (response.statusCode == 200) {
        await fetchPresets(projectId);
      } else {
        throw Exception('Failed to save preset: ${response.body}');
      }
    } catch (error) {
      print('Error saving preset: $error');
      rethrow;
    }
  }

  Future<void> deletePreset(String presetName, String projectId) async {
    try {
      final response = await http.delete(
        Uri.parse(
            '$apiUrl/presets/${Uri.encodeComponent(presetName)}?project_id=$projectId'),
        headers: await getAuthHeaders(),
      );

      if (response.statusCode == 200) {
        _presets.remove(presetName);
        if (_selectedPreset == presetName) {
          _selectedPreset = null;
          _currentPreset = null;
        }
        notifyListeners();
      } else {
        throw Exception('Failed to delete preset');
      }
    } catch (error) {
      print('Error deleting preset: $error');
      rethrow;
    }
  }
}
