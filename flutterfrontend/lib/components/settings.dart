import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';

class Settings extends StatefulWidget {
  const Settings({Key? key}) : super(key: key);

  @override
  State<Settings> createState() => _SettingsState();
}

class _SettingsState extends State<Settings> {
  final _formKey = GlobalKey<FormState>();
  String _apiKey = '';
  bool _isKeySet = false;
  bool _isEditingApiKey = false;
  Map<String, String> _modelSettings = {
    'mainLLM': 'gemini-1.5-pro-002',
    'checkLLM': 'gemini-1.5-pro-002',
    'embeddingsModel': 'models/text-embedding-004',
    'titleGenerationLLM': 'gemini-1.5-pro-002',
    'CodexExtractionLLM': 'gemini-1.5-pro-002',
    'knowledgeBaseQueryLLM': 'gemini-1.5-pro-002',
  };
  final List<String> _modelOptions = [
    'gemini-1.5-pro-002',
    'gemini-1.5-flash-002',
    'gemini-1.5-flash-8b',
  ];
  final List<String> _embeddingsOptions = [
    'models/embedding-001',
    'models/text-embedding-004',
  ];

  @override
  void initState() {
    super.initState();
    _checkApiKey();
    _fetchModelSettings();
  }

  Future<void> _checkApiKey() async {
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/settings/api-key'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (mounted) { // Check if the widget is still mounted
          setState(() {
            _isKeySet = data['isSet'];
            _apiKey = data['apiKey'] ?? '';
          });
        }
      } else {
        Fluttertoast.showToast(msg: 'Error checking API key');
      }
    } catch (error) {
      print('Error checking API key: $error');
      Fluttertoast.showToast(msg: 'Error checking API key');
    }
  }

  Future<void> _fetchModelSettings() async {
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/settings/model'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 200) {
        if (mounted) { // Check if the widget is still mounted
          setState(() {
            _modelSettings = Map<String, String>.from(json.decode(response.body));
          });
        }
      } else {
        Fluttertoast.showToast(msg: 'Error fetching model settings');
      }
    } catch (error) {
      print('Error fetching model settings: $error');
      Fluttertoast.showToast(msg: 'Error fetching model settings');
    }
  }

  Future<void> _handleSaveApiKey() async {
    try {
      final response = await http.post(
        Uri.parse('$apiUrl/settings/api-key'),
        headers: await getAuthHeaders(),
        body: json.encode({'apiKey': _apiKey}),
      );
      if (response.statusCode == 200) {
        if (mounted) { // Check if the widget is still mounted
          setState(() {
            _isKeySet = true;
            _isEditingApiKey = false;
          });
        }
        Fluttertoast.showToast(msg: 'API key saved successfully');
      } else {
        Fluttertoast.showToast(msg: 'Error saving API key');
      }
    } catch (error) {
      print('Error saving API key: $error');
      Fluttertoast.showToast(msg: 'Error saving API key');
    }
  }

  Future<void> _handleRemoveApiKey() async {
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/settings/api-key'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 204) {
        if (mounted) { // Check if the widget is still mounted
          setState(() {
            _isKeySet = false;
            _apiKey = '';
          });
        }
        Fluttertoast.showToast(msg: 'API key removed successfully');
      } else {
        Fluttertoast.showToast(msg: 'Error removing API key');
      }
    } catch (error) {
      print('Error removing API key: $error');
      Fluttertoast.showToast(msg: 'Error removing API key');
    }
  }

  Future<void> _handleSaveModelSettings() async {
    try {
      final response = await http.post(
        Uri.parse('$apiUrl/settings/model'),
        headers: await getAuthHeaders(),
        body: json.encode(_modelSettings),
      );
      if (response.statusCode == 200) {
        Fluttertoast.showToast(msg: 'Model settings saved successfully');
      } else {
        Fluttertoast.showToast(msg: 'Error saving model settings');
      }
    } catch (error) {
      print('Error saving model settings: $error');
      Fluttertoast.showToast(msg: 'Error saving model settings');
    }
  }

  void _handleModelChange(String setting, String value) {
    setState(() {
      _modelSettings[setting] = value;
    });
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: const Color(0xFF212529),
          borderRadius: BorderRadius.circular(8),
          boxShadow: const [
            BoxShadow(
              color: Color(0x1A000000),
              blurRadius: 4,
              offset: Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Settings',
              style: TextStyle(
                color: Color(0xFF007bff),
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 20),
            Card(
              color: const Color(0xFF343a40),
              child: Padding(
                padding: const EdgeInsets.all(20.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'API Key',
                      style: TextStyle(
                        color: Color(0xFF007bff),
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 10),
                    if (_isKeySet && !_isEditingApiKey)
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('API Key: $_apiKey'),
                          const SizedBox(height: 10),
                          Row(
                            children: [
                              ElevatedButton(
                                onPressed: () => setState(() => _isEditingApiKey = true),
                                child: const Text('Edit API Key'),
                              ),
                              const SizedBox(width: 10),
                              ElevatedButton(
                                onPressed: _handleRemoveApiKey,
                                child: const Text('Remove API Key'),
                              ),
                            ],
                          ),
                        ],
                      )
                    else
                      Column(
                        children: [
                          TextFormField(
                            initialValue: _apiKey,
                            onChanged: (value) => setState(() => _apiKey = value),
                            obscureText: true,
                            decoration: const InputDecoration(
                              labelText: 'API Key',
                              labelStyle: TextStyle(color: Colors.white),
                              enabledBorder: OutlineInputBorder(
                                borderSide: BorderSide(color: Color(0xFFced4da)),
                              ),
                              focusedBorder: OutlineInputBorder(
                                borderSide: BorderSide(color: Color(0xFF007bff)),
                              ),
                            ),
                            style: const TextStyle(color: Colors.white),
                          ),
                          const SizedBox(height: 10),
                          ElevatedButton(
                            onPressed: _handleSaveApiKey,
                            child: const Text('Save API Key'),
                          ),
                        ],
                      ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 20),
            Card(
              color: const Color(0xFF343a40),
              child: Padding(
                padding: const EdgeInsets.all(20.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Model Settings',
                      style: TextStyle(
                        color: Color(0xFF007bff),
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 10),
                    ..._modelSettings.entries.map((entry) {
                      final setting = entry.key;
                      final value = entry.value;
                      final options = setting == 'embeddingsModel' ? _embeddingsOptions : _modelOptions;
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('$setting: $value'),
                          DropdownButtonFormField<String>(
                            value: value,
                            onChanged: (newValue) => _handleModelChange(setting, newValue!),
                            items: options.map((option) {
                              return DropdownMenuItem<String>(
                                value: option,
                                child: Text(option),
                              );
                            }).toList(),
                            decoration: const InputDecoration(
                              enabledBorder: OutlineInputBorder(
                                borderSide: BorderSide(color: Color(0xFFced4da)),
                              ),
                              focusedBorder: OutlineInputBorder(
                                borderSide: BorderSide(color: Color(0xFF007bff)),
                              ),
                            ),
                          ),
                          const SizedBox(height: 10),
                        ],
                      );
                    }).toList(),
                    ElevatedButton(
                      onPressed: _handleSaveModelSettings,
                      child: const Text('Save Model Settings'),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
