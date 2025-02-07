import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:logging/logging.dart';

final _logger = Logger('Settings');

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
  Map<String, dynamic> _modelSettings = {
    'mainLLM': 'gemini-1.5-pro-002',
    'checkLLM': 'gemini-1.5-pro-002',
    'embeddingsModel': 'models/text-embedding-004',
    'titleGenerationLLM': 'gemini-1.5-pro-002',
    'extractionLLM': 'gemini-1.5-pro-002',
    'knowledgeBaseQueryLLM': 'gemini-1.5-pro-002',
    'temperature': 0.7,
  };
  final List<String> _modelOptions = [
    'gemini-2.0-flash',
    'gemini-2.0-flash-thinking-exp-01-21',
    'gemini-2.0-pro-exp-02-05',
    'gemini-2.0-flash-lite-preview-02-05',
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
        final data = json.decode(utf8.decode(response.bodyBytes));
        if (mounted) {
          // Check if the widget is still mounted
          setState(() {
            _isKeySet = data['isSet'];
            _apiKey = data['apiKey'] ?? '';
          });
        }
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Error checking API key')));
      }
    } catch (error) {
      _logger.severe('Error checking API key: $error');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Error checking API key')));
    }
  }

  Future<void> _fetchModelSettings() async {
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/settings/model'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 200) {
        if (mounted) {
          setState(() {
            final fetchedSettings = Map<String, dynamic>.from(
                json.decode(utf8.decode(response.bodyBytes)));
            if (fetchedSettings['temperature'] != null) {
              fetchedSettings['temperature'] =
                  double.parse(fetchedSettings['temperature'].toString());
            } else {
              fetchedSettings['temperature'] = 0.7;
            }
            _modelSettings = fetchedSettings;
          });
        }
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Error fetching model settings')));
      }
    } catch (error) {
      _logger.severe('Error fetching model settings: $error');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Error fetching model settings')));
    }
  }

  Future<void> _handleSaveApiKey() async {
    try {
      final response = await http.post(
        Uri.parse('$apiUrl/settings/api-key'),
        headers: await getAuthHeaders(),
        body: utf8.encode(json.encode({'apiKey': _apiKey})),
      );
      if (response.statusCode == 200) {
        if (mounted) {
          // Check if the widget is still mounted
          setState(() {
            _isKeySet = true;
            _isEditingApiKey = false;
          });
        }
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('API key saved successfully')));
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Error saving API key')));
      }
    } catch (error) {
      _logger.severe('Error saving API key: $error');
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Error saving API key')));
    }
  }

  Future<void> _handleRemoveApiKey() async {
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/settings/api-key'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 204) {
        if (mounted) {
          // Check if the widget is still mounted
          setState(() {
            _isKeySet = false;
            _apiKey = '';
          });
        }
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('API key removed successfully')));
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Error removing API key')));
      }
    } catch (error) {
      _logger.severe('Error removing API key: $error');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Error removing API key')));
    }
  }

  Future<void> _handleSaveModelSettings() async {
    try {
      final settingsToSave = Map<String, dynamic>.from(_modelSettings);

      final response = await http.post(
        Uri.parse('$apiUrl/settings/model'),
        headers: await getAuthHeaders(),
        body: utf8.encode(json.encode(settingsToSave)),
      );

      if (response.statusCode == 200) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Model settings saved successfully')));
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Error saving model settings')));
      }
    } catch (error) {
      _logger.severe('Error saving model settings: $error');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Error saving model settings')));
    }
  }

  void _handleModelChange(String setting, String value) {
    setState(() {
      _modelSettings[setting] = value;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildApiKeySection(),
          const SizedBox(height: 32),
          _buildModelSettingsSection(),
        ],
      ),
    );
  }

  Widget _buildApiKeySection() {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: Theme.of(context).colorScheme.outline.withOpacity(0.2),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.key,
                  size: 20,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Text(
                  'API Key',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: Theme.of(context).colorScheme.primary,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (_isKeySet && !_isEditingApiKey)
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildSecureKeyDisplay(),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      FilledButton.tonalIcon(
                        onPressed: () =>
                            setState(() => _isEditingApiKey = true),
                        icon: const Icon(Icons.edit),
                        label: const Text('Edit Key'),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton.icon(
                        onPressed: _handleRemoveApiKey,
                        icon: const Icon(Icons.delete),
                        label: const Text('Remove'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: Theme.of(context).colorScheme.error,
                        ),
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
                    decoration: InputDecoration(
                      labelText: 'Enter API Key',
                      hintText: 'Your API key',
                      prefixIcon: const Icon(Icons.vpn_key),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Align(
                    alignment: Alignment.centerRight,
                    child: FilledButton.icon(
                      onPressed: _handleSaveApiKey,
                      icon: const Icon(Icons.save),
                      label: const Text('Save Key'),
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildModelSettingsSection() {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: Theme.of(context).colorScheme.outline.withOpacity(0.2),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.tune,
                  size: 20,
                  color: Theme.of(context).colorScheme.secondary,
                ),
                const SizedBox(width: 8),
                Text(
                  'Model Settings',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: Theme.of(context).colorScheme.secondary,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 24),
            _buildTemperatureSlider(),
            const SizedBox(height: 24),
            ..._modelSettings.entries
                .where((entry) => entry.key != 'temperature')
                .map((entry) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _formatSettingName(entry.key),
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                  const SizedBox(height: 8),
                  DropdownButtonFormField<String>(
                    value: entry.value,
                    onChanged: (newValue) =>
                        _handleModelChange(entry.key, newValue!),
                    items: (entry.key == 'embeddingsModel'
                            ? _embeddingsOptions
                            : _modelOptions)
                        .map((option) {
                      return DropdownMenuItem<String>(
                        value: option,
                        child: Text(option),
                      );
                    }).toList(),
                    decoration: InputDecoration(
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                ],
              );
            }).toList(),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton.icon(
                onPressed: _handleSaveModelSettings,
                icon: const Icon(Icons.save),
                label: const Text('Save Settings'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSecureKeyDisplay() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(
            Icons.check_circle,
            size: 16,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(width: 8),
          Text(
            'API Key is set and secured',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildTemperatureSlider() {
    final temperature = (_modelSettings['temperature'] as num).toDouble();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Temperature',
          style: Theme.of(context).textTheme.titleSmall,
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: Slider(
                value: temperature,
                min: 0.0,
                max: 2.0,
                divisions: 20,
                label: temperature.toStringAsFixed(2),
                onChanged: (value) {
                  setState(() {
                    _modelSettings['temperature'] = value;
                  });
                },
              ),
            ),
            SizedBox(
              width: 60,
              child: Text(
                temperature.toStringAsFixed(2),
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
          ],
        ),
      ],
    );
  }

  String _formatSettingName(String name) {
    return name
        .replaceAllMapped(
          RegExp(r'([A-Z])'),
          (match) => ' ${match.group(1)}',
        )
        .split('LLM')
        .join(' Model')
        .trim()
        .split(' ')
        .map((word) => word[0].toUpperCase() + word.substring(1))
        .join(' ');
  }
}
