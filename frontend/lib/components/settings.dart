import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:dropdown_search/dropdown_search.dart';

import '../utils/constants.dart';
import 'package:logging/logging.dart';

final _logger = Logger('Settings');

// Define a simple model structure for clarity
class ModelInfo {
  final String id;
  final String name;

  ModelInfo({required this.id, required this.name});

  // Factory constructor for JSON parsing (optional but good practice)
  factory ModelInfo.fromJson(Map<String, dynamic> json) {
    return ModelInfo(
      id: json['id'] as String,
      name: json['name'] as String,
    );
  }
  // For DropdownSearch comparison
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ModelInfo && runtimeType == other.runtimeType && id == other.id;

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() => name; // Important for default display in DropdownSearch
}

class Settings extends StatefulWidget {
  const Settings({Key? key}) : super(key: key);

  @override
  State<Settings> createState() => _SettingsState();
}

class _SettingsState extends State<Settings> {
  final _formKey = GlobalKey<FormState>();

  // Google API Key State
  String _apiKey = '';
  bool _isKeySet = false;
  bool _isEditingApiKey = false;

  // OpenRouter API Key State
  String _openRouterApiKey = '';
  bool _isOpenRouterKeySet = false;
  bool _isEditingOpenRouterApiKey = false;

  // Model Settings State
  Map<String, dynamic> _modelSettings = {
    'mainLLM': 'gemini-1.5-pro-latest', // Default will be updated after fetch
    'checkLLM': 'gemini-1.5-flash-latest',
    'embeddingsModel': 'models/text-embedding-004',
    'titleGenerationLLM': 'gemini-1.5-flash-latest',
    'extractionLLM': 'gemini-1.5-flash-latest',
    'knowledgeBaseQueryLLM': 'gemini-1.5-flash-latest',
    'temperature': 0.7,
  };

  // Available Models State
  List<ModelInfo> _availableModels = [];
  bool _isLoadingModels = false;
  String _selectedProviderFilter = "All"; // Added state for filtering

  // Hardcoded Embedding Options
  final List<ModelInfo> _embeddingsOptions = [
    ModelInfo(
        id: 'models/text-embedding-004', name: 'Google: text-embedding-004'),
    ModelInfo(
        id: 'models/embedding-001', name: 'Google: embedding-001 (Legacy)'),
  ];

  // Specific Google Gemini Models via Google API
  final List<ModelInfo> _googleModels = [
    ModelInfo(
        id: 'gemini-1.5-pro-latest', name: 'Google: Gemini 1.5 Pro (Latest)'),
    ModelInfo(
        id: 'gemini-1.5-flash-latest',
        name: 'Google: Gemini 1.5 Flash (Latest)'),

    ModelInfo(id: 'gemini-1.0-pro', name: 'Google: Gemini 1.0 Pro'),
    ModelInfo(id: 'gemini-1.5-flash-8b', name: 'Google: Gemini 1.5 Flash 8B'),
    // Experimental / Specific Models
    ModelInfo(
        id: 'gemini-2.5-pro-exp-03-25',
        name: 'Google: Gemini 2.5 Pro Exp 03-25'),
    ModelInfo(
        id: 'gemini-2.0-pro-exp-02-05',
        name: 'Google: Gemini 2.0 Pro Exp 02-05'),
    ModelInfo(
        id: 'gemini-2.0-flash-thinking-exp-01-21',
        name: 'Google: Gemini 2.0 Flash Thinking Exp 01-21'),
    ModelInfo(id: 'gemini-2.0-flash', name: 'Google: Gemini 2.0 Flash'),
    ModelInfo(
        id: 'gemini-2.0-flash-lite', name: 'Google: Gemini 2.0 Flash Lite'),
  ];

  @override
  void initState() {
    super.initState();
    _checkApiKey();
    _checkOpenRouterApiKey();
    _fetchAllModels(); // Fetch models on init
    _fetchModelSettings(); // Fetch saved settings AFTER models potentially loaded
  }

  // --- Google API Key Functions ---
  Future<void> _checkApiKey() async {
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/settings/api-key'),
      );
      if (response.statusCode == 200) {
        final data = json.decode(utf8.decode(response.bodyBytes));
        if (mounted) {
          setState(() {
            _isKeySet = data['isSet'];
            _apiKey = data['apiKey'] ?? ''; // Use Google API key state
          });
        }
      } else {
        _handleApiError('Error checking Google API key');
      }
    } catch (error) {
      _handleApiError('Error checking Google API key', error);
    }
  }

  Future<void> _handleSaveApiKey() async {
    try {
      final response = await http.post(
        Uri.parse('$apiUrl/settings/api-key'),
        headers: {'Content-Type': 'application/json; charset=utf-8'},
        body: utf8.encode(
            json.encode({'apiKey': _apiKey})), // Use Google API key state
      );
      if (response.statusCode == 200) {
        if (mounted) {
          setState(() {
            _isKeySet = true;
            _isEditingApiKey = false;
          });
        }
        _showSuccessSnackbar('Google API key saved successfully');
      } else {
        _handleApiError('Error saving Google API key');
      }
    } catch (error) {
      _handleApiError('Error saving Google API key', error);
    }
  }

  Future<void> _handleRemoveApiKey() async {
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/settings/api-key'),
      );
      // Check for 200 or 204 No Content
      if (response.statusCode == 200 || response.statusCode == 204) {
        if (mounted) {
          setState(() {
            _isKeySet = false;
            _apiKey = ''; // Use Google API key state
            _isEditingApiKey = false;
          });
        }
        _showSuccessSnackbar('Google API key removed successfully');
      } else {
        _handleApiError('Error removing Google API key');
      }
    } catch (error) {
      _handleApiError('Error removing Google API key', error);
    }
  }

  // --- OpenRouter API Key Functions ---
  Future<void> _checkOpenRouterApiKey() async {
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/settings/openrouter-api-key'), // Use new endpoint
      );
      if (response.statusCode == 200) {
        final data = json.decode(utf8.decode(response.bodyBytes));
        if (mounted) {
          setState(() {
            _isOpenRouterKeySet = data['isSet'];
            _openRouterApiKey =
                data['apiKey'] ?? ''; // Use OpenRouter API key state
          });
        }
      } else {
        _handleApiError('Error checking OpenRouter API key');
      }
    } catch (error) {
      _handleApiError('Error checking OpenRouter API key', error);
    }
  }

  Future<void> _handleSaveOpenRouterApiKey() async {
    try {
      final response = await http.post(
        Uri.parse('$apiUrl/settings/openrouter-api-key'), // Use new endpoint
        headers: {'Content-Type': 'application/json; charset=utf-8'},
        body: utf8.encode(json.encode(
            {'apiKey': _openRouterApiKey})), // Use OpenRouter API key state
      );
      if (response.statusCode == 200) {
        if (mounted) {
          setState(() {
            _isOpenRouterKeySet = true;
            _isEditingOpenRouterApiKey = false;
          });
        }
        _showSuccessSnackbar('OpenRouter API key saved successfully');
      } else {
        _handleApiError('Error saving OpenRouter API key');
      }
    } catch (error) {
      _handleApiError('Error saving OpenRouter API key', error);
    }
  }

  Future<void> _handleRemoveOpenRouterApiKey() async {
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/settings/openrouter-api-key'), // Use new endpoint
      );
      // Check for 200 or 204 No Content
      if (response.statusCode == 200 || response.statusCode == 204) {
        if (mounted) {
          setState(() {
            _isOpenRouterKeySet = false;
            _openRouterApiKey = ''; // Use OpenRouter API key state
            _isEditingOpenRouterApiKey = false;
          });
        }
        _showSuccessSnackbar('OpenRouter API key removed successfully');
      } else {
        _handleApiError('Error removing OpenRouter API key');
      }
    } catch (error) {
      _handleApiError('Error removing OpenRouter API key', error);
    }
  }

  // --- Model Fetching ---
  Future<void> _fetchAllModels() async {
    if (!mounted) return;
    setState(() {
      _isLoadingModels = true;
    });

    List<ModelInfo> openRouterModels = [];
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/settings/openrouter-models'),
      );
      if (response.statusCode == 200) {
        List<dynamic> fetchedData =
            json.decode(utf8.decode(response.bodyBytes));
        openRouterModels = fetchedData
            .map((modelJson) => ModelInfo.fromJson(modelJson))
            .toList();
      } else {
        _handleApiError('Error fetching OpenRouter models list');
      }
    } catch (error) {
      _handleApiError('Error fetching OpenRouter models list', error);
    }

    if (!mounted) return;
    setState(() {
      _availableModels = [..._googleModels, ...openRouterModels];
      _availableModels
          .sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
      _isLoadingModels = false;
      _validateModelSettings();
    });
  }

  // --- Model Settings Functions ---
  Future<void> _fetchModelSettings() async {
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/settings/model'),
      );
      if (response.statusCode == 200) {
        if (mounted) {
          // Store fetched settings temporarily
          final fetchedSettings = Map<String, dynamic>.from(
              json.decode(utf8.decode(response.bodyBytes)));
          // Ensure temperature is double and provide default
          fetchedSettings['temperature'] =
              (fetchedSettings['temperature'] as num?)?.toDouble() ?? 0.7;

          setState(() {
            _modelSettings = fetchedSettings; // Apply fetched settings
            _validateModelSettings(); // Validate against potentially loaded models
          });
        }
      } else {
        _handleApiError('Error fetching model settings');
      }
    } catch (error) {
      _handleApiError('Error fetching model settings', error);
    }
  }

  // New validation function to run after models are fetched or settings loaded
  void _validateModelSettings() {
    if (_availableModels.isEmpty && !_isLoadingModels) {
      _logger.warning("Models not loaded yet, cannot validate settings.");
      // Maybe show a loading indicator or disable dropdowns until models load
      return;
    }
    if (_availableModels.isEmpty && _isLoadingModels) {
      _logger.info("Still loading models, validation skipped for now.");
      return;
    }

    final availableModelIds = _availableModels.map((m) => m.id).toSet();
    final availableEmbeddingIds = _embeddingsOptions.map((m) => m.id).toSet();
    bool changed = false;

    [
      'mainLLM',
      'checkLLM',
      'titleGenerationLLM',
      'extractionLLM',
      'knowledgeBaseQueryLLM'
    ].forEach((key) {
      if (!_modelSettings.containsKey(key) ||
          !availableModelIds.contains(_modelSettings[key])) {
        _logger.warning(
            "Invalid or missing model for '$key': ${_modelSettings[key]}. Resetting to default.");
        _modelSettings[key] =
            _availableModels.first.id; // Default to first available model ID
        changed = true;
      }
    });

    if (!_modelSettings.containsKey('embeddingsModel') ||
        !availableEmbeddingIds.contains(_modelSettings['embeddingsModel'])) {
      _logger.warning(
          "Invalid or missing embedding model: ${_modelSettings['embeddingsModel']}. Resetting to default.");
      _modelSettings['embeddingsModel'] =
          _embeddingsOptions.first.id; // Default to first embedding
      changed = true;
    }

    if (changed && mounted) {
      setState(() {}); // Update UI if defaults were applied
    }
  }

  Future<void> _handleSaveModelSettings() async {
    try {
      final settingsToSave = Map<String, dynamic>.from(_modelSettings);

      final response = await http.post(
        Uri.parse('$apiUrl/settings/model'),
        headers: {'Content-Type': 'application/json; charset=utf-8'},
        body: utf8.encode(json.encode(settingsToSave)),
      );

      if (response.statusCode == 200) {
        _showSuccessSnackbar('Model settings saved successfully');
      } else {
        _handleApiError('Error saving model settings');
      }
    } catch (error) {
      _handleApiError('Error saving model settings', error);
    }
  }

  // --- UI Helpers ---

  void _showSuccessSnackbar(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  void _handleApiError(String message, [dynamic error]) {
    _logger.severe('$message: $error');
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  void _handleModelChange(String setting, ModelInfo? value) {
    if (value == null) return;

    // Check if the selected value is valid for the setting type
    bool isValidOption = false;
    if (setting == 'embeddingsModel') {
      isValidOption = _embeddingsOptions.any((m) => m.id == value.id);
    } else {
      isValidOption = _availableModels.any((m) => m.id == value.id);
    }

    if (!isValidOption) {
      _logger.warning(
          "Attempted to set invalid model option: ${value.id} for $setting");
      return;
    }

    setState(() {
      _modelSettings[setting] = value.id; // Store the ID
    });
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildApiKeySection(), // Google API Key
          const SizedBox(height: 16), // Add space between key sections
          _buildOpenRouterApiKeySection(), // OpenRouter API Key - TO BE ADDED
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
                  'Google API Key',
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
                  _buildSecureKeyDisplay('Google API Key'),
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
                      labelText: 'Enter Google API Key',
                      hintText: 'Your Google API key',
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

  Widget _buildOpenRouterApiKeySection() {
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
                  color: Theme.of(context).colorScheme.tertiary,
                ),
                const SizedBox(width: 8),
                Text(
                  'OpenRouter API Key',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: Theme.of(context).colorScheme.tertiary,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (_isOpenRouterKeySet && !_isEditingOpenRouterApiKey)
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildSecureKeyDisplay('OpenRouter API Key'),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      FilledButton.tonalIcon(
                        onPressed: () =>
                            setState(() => _isEditingOpenRouterApiKey = true),
                        icon: const Icon(Icons.edit),
                        label: const Text('Edit Key'),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton.icon(
                        onPressed: _handleRemoveOpenRouterApiKey,
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
                    initialValue: _openRouterApiKey,
                    onChanged: (value) =>
                        setState(() => _openRouterApiKey = value),
                    obscureText: true,
                    decoration: InputDecoration(
                      labelText: 'Enter OpenRouter API Key',
                      hintText: 'Your OpenRouter API key (sk-or-...)',
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
                      onPressed: _handleSaveOpenRouterApiKey,
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
    // Dynamically determine providers for filtering
    final Set<String> providers = {"All", "Google"};
    for (var model in _availableModels) {
      if (model.id.startsWith('openrouter/')) {
        final parts = model.id.split('/');
        if (parts.length > 1) {
          // Capitalize provider name for display
          final providerName =
              parts[1][0].toUpperCase() + parts[1].substring(1);
          providers.add("OpenRouter/$providerName");
        }
      }
    }
    final sortedProviders = providers.toList()..sort();

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
        child: _isLoadingModels
            ? const Center(child: CircularProgressIndicator(strokeWidth: 2))
            : Column(
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
                        style: Theme.of(context)
                            .textTheme
                            .titleMedium
                            ?.copyWith(
                              color: Theme.of(context).colorScheme.secondary,
                            ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  // --- Add Filter Chips ---
                  Text("Filter by Provider:",
                      style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8.0, // Horizontal space between chips
                    runSpacing: 4.0, // Vertical space between lines
                    children: sortedProviders.map((provider) {
                      return FilterChip(
                        label: Text(provider),
                        selected: _selectedProviderFilter == provider,
                        onSelected: (selected) {
                          setState(() {
                            _selectedProviderFilter = provider;
                          });
                        },
                        selectedColor:
                            Theme.of(context).colorScheme.secondaryContainer,
                        checkmarkColor:
                            Theme.of(context).colorScheme.onSecondaryContainer,
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 24),
                  // --- Temperature Slider ---
                  _buildTemperatureSlider(),
                  const SizedBox(height: 24),
                  // --- Model Dropdowns ---
                  ..._modelSettings.entries
                      .where((entry) => entry.key != 'temperature')
                      .map((entry) {
                    // Use the appropriate list based on the setting key
                    final baseOptionsList = entry.key == 'embeddingsModel'
                        ? _embeddingsOptions
                        : _availableModels;

                    // Find the currently selected ModelInfo object
                    final selectedValue = baseOptionsList.firstWhere(
                        (model) => model.id == _modelSettings[entry.key],
                        orElse: () {
                      _logger.warning(
                          "Selected model ID '${_modelSettings[entry.key]}' for setting '${entry.key}' not found in options. Defaulting.");
                      return baseOptionsList.isNotEmpty
                          ? baseOptionsList.first
                          : ModelInfo(id: 'error', name: 'Error - No Models');
                    });

                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _formatSettingName(entry.key),
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                        const SizedBox(height: 8),
                        DropdownSearch<ModelInfo>(
                          asyncItems: (String filter) async {
                            await Future.delayed(
                                const Duration(milliseconds: 50));

                            List<ModelInfo> providerFilteredList;
                            if (_selectedProviderFilter == "All") {
                              providerFilteredList = baseOptionsList;
                            } else if (_selectedProviderFilter == "Google") {
                              providerFilteredList = baseOptionsList
                                  .where((model) =>
                                      !model.id.startsWith('openrouter/'))
                                  .toList();
                            } else {
                              final providerKey = _selectedProviderFilter
                                  .split('/')
                                  .last
                                  .toLowerCase();
                              providerFilteredList = baseOptionsList
                                  .where((model) =>
                                      model.id.startsWith('openrouter/') &&
                                      model.id.split('/')[1].toLowerCase() ==
                                          providerKey)
                                  .toList();
                            }

                            if (filter.isEmpty) {
                              return providerFilteredList;
                            }
                            return providerFilteredList
                                .where((model) => model.name
                                    .toLowerCase()
                                    .contains(filter.toLowerCase()))
                                .toList();
                          },
                          selectedItem: selectedValue,
                          onChanged: (ModelInfo? newValue) {
                            _handleModelChange(entry.key, newValue);
                          },
                          dropdownDecoratorProps: DropDownDecoratorProps(
                            dropdownSearchDecoration: InputDecoration(
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(8),
                              ),
                              contentPadding: const EdgeInsets.symmetric(
                                horizontal: 16,
                                vertical: 8,
                              ),
                            ),
                          ),
                          popupProps: PopupProps.menu(
                            showSearchBox: true,
                            searchFieldProps: TextFieldProps(
                              decoration: InputDecoration(
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                contentPadding: const EdgeInsets.symmetric(
                                    horizontal: 16, vertical: 12),
                                hintText: "Search models...",
                              ),
                              autofocus: true,
                            ),
                            itemBuilder: (context, model, isSelected) {
                              return ListTile(
                                title: Text(model.name),
                                selected: isSelected,
                              );
                            },
                            menuProps: MenuProps(
                              borderRadius: BorderRadius.circular(8),
                            ),
                            constraints: const BoxConstraints(maxHeight: 300),
                          ),
                          itemAsString: (ModelInfo u) => u.name,
                          compareFn: (ModelInfo i, ModelInfo s) => i == s,
                        ),
                        const SizedBox(height: 16),
                      ],
                    );
                  }).toList(),
                  // ... (Save Button) ...
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

  Widget _buildSecureKeyDisplay(String label) {
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
            '$label is set and secured',
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
