import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import '../utils/notifications.dart';

class CodexGeneration extends StatefulWidget {
  final String projectId;

  const CodexGeneration({Key? key, required this.projectId}) : super(key: key);

  @override
  State<CodexGeneration> createState() => _CodexGenerationState();
}

class _CodexGenerationState extends State<CodexGeneration> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _descriptionController = TextEditingController();

  final List<String> _types = [
    'worldbuilding',
    'character',
    'item',
    'lore',
    'faction'
  ];
  final Map<String, List<String>> _subtypes = {
    'worldbuilding': ['history', 'culture', 'geography'],
    'character': [],
    'item': [],
    'lore': [],
    'faction': [],
  };

  @override
  void initState() {
    super.initState();
    final appState = Provider.of<AppState>(context, listen: false);

    // Initialize with saved state
    _descriptionController.text = appState.codexGenerationState['description'];

    // Add listener to update state when text changes
    _descriptionController.addListener(() {
      appState.updateCodexGenerationField(
          'description', _descriptionController.text);
    });
  }

  @override
  void dispose() {
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _handleSubmit() async {
    if (_formKey.currentState!.validate()) {
      final appState = Provider.of<AppState>(context, listen: false);
      appState.updateCodexGenerationProgress(isGenerating: true);

      try {
        final headers = {...await getAuthHeaders()};

        final requestBody = {
          'codex_type': appState.codexGenerationState['type'],
          'subtype': appState.codexGenerationState['subtype'],
          'description': appState.codexGenerationState['description'],
        };

        final response = await http.post(
          Uri.parse('$apiUrl/codex/generate?project_id=${widget.projectId}'),
          headers: headers,
          body: utf8.encode(json.encode(requestBody)),
        );

        if (response.statusCode == 200) {
          final data = json.decode(utf8.decode(response.bodyBytes));
          appState.updateCodexGenerationProgress(
            isGenerating: false,
            generatedItem: data['item'],
          );
          AppNotification.show(context, 'Codex item generated successfully');
        } else {
          appState.updateCodexGenerationProgress(isGenerating: false);
          AppNotification.show(
              context, 'Error generating codex item: ${response.body}');
        }
      } catch (error) {
        appState.updateCodexGenerationProgress(isGenerating: false);
        print('Error generating codex item: $error');
        AppNotification.show(context, 'Error generating codex item: $error');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        final generationState = appState.codexGenerationState;
        final isGenerating = generationState['isGenerating'];
        final generatedItem = generationState['generatedItem'];

        return Padding(
          padding: const EdgeInsets.all(24),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Generation Form
              Expanded(
                flex: 1,
                child: SingleChildScrollView(
                  child: Card(
                    elevation: 4,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _buildHeader(),
                          const SizedBox(height: 24),
                          _buildGenerationForm(isGenerating),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 24),
              // Generated Result
              if (generatedItem != null)
                Expanded(
                  flex: 1,
                  child: SingleChildScrollView(
                    child: _buildGeneratedResult(generatedItem),
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildHeader() {
    return Row(
      children: [
        Icon(
          Icons.auto_awesome,
          color: Theme.of(context).colorScheme.primary,
          size: 32,
        ),
        const SizedBox(width: 16),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Generate Codex Item',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            Text(
              'Create new content for your story',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context)
                        .colorScheme
                        .onSurface
                        .withOpacity(0.6),
                  ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildGenerationForm(bool isGenerating) {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        return Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _buildTypeDropdown(),
              const SizedBox(height: 16),
              if (appState.codexGenerationState['type'] == 'worldbuilding') ...[
                _buildSubtypeDropdown(),
                const SizedBox(height: 16),
              ],
              _buildDescriptionField(),
              const SizedBox(height: 24),
              _buildGenerateButton(isGenerating),
            ],
          ),
        );
      },
    );
  }

  Widget _buildTypeDropdown() {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        return DropdownButtonFormField<String>(
          value: appState.codexGenerationState['type'],
          decoration: InputDecoration(
            labelText: 'Type',
            prefixIcon: const Icon(Icons.category),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
            ),
          ),
          items: _types.map((type) {
            return DropdownMenuItem<String>(
              value: type,
              key: ValueKey(type),
              child: Text(type.capitalize()),
            );
          }).toList(),
          onChanged: (value) {
            appState.updateCodexGenerationField('type', value);
            appState.updateCodexGenerationField('subtype', null);
          },
        );
      },
    );
  }

  Widget _buildSubtypeDropdown() {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        return DropdownButtonFormField<String>(
          value: appState.codexGenerationState['subtype'],
          decoration: InputDecoration(
            labelText: 'Subtype',
            prefixIcon: const Icon(Icons.subdirectory_arrow_right),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
            ),
          ),
          items:
              _subtypes[appState.codexGenerationState['type']]!.map((subtype) {
            return DropdownMenuItem<String>(
              value: subtype,
              child: Text(subtype.capitalize()),
            );
          }).toList(),
          onChanged: (value) {
            appState.updateCodexGenerationField('subtype', value);
          },
        );
      },
    );
  }

  Widget _buildDescriptionField() {
    return TextFormField(
      decoration: InputDecoration(
        labelText: 'Description',
        hintText: 'Describe what you want to generate...',
        prefixIcon: const Icon(Icons.description),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
      maxLines: 4,
      controller: _descriptionController,
      validator: (value) {
        if (value == null || value.isEmpty) {
          return 'Please enter a description';
        }
        return null;
      },
    );
  }

  Widget _buildGenerateButton(bool isGenerating) {
    return ElevatedButton.icon(
      onPressed: isGenerating ? null : _handleSubmit,
      icon: isGenerating
          ? const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : const Icon(Icons.auto_awesome),
      label: Text(isGenerating ? 'Generating...' : 'Generate'),
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 16),
      ),
    );
  }

  Widget _buildGeneratedResult(dynamic generatedItem) {
    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.star,
                  color: Theme.of(context).colorScheme.secondary,
                  size: 32,
                ),
                const SizedBox(width: 16),
                Text(
                  'Generated Item',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ],
            ),
            const SizedBox(height: 24),
            _buildResultField('Name', generatedItem['name']),
            const SizedBox(height: 16),
            _buildResultField('Description', generatedItem['description']),
            const SizedBox(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                OutlinedButton.icon(
                  onPressed: () {
                    final appState =
                        Provider.of<AppState>(context, listen: false);
                    appState.resetCodexGenerationState();
                  },
                  icon: const Icon(Icons.refresh),
                  label: const Text('Generate Another'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResultField(String label, String content) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                color: Theme.of(context).colorScheme.primary,
              ),
        ),
        const SizedBox(height: 8),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: Theme.of(context).dividerColor,
            ),
          ),
          child: Text(content),
        ),
      ],
    );
  }
}

extension StringExtension on String {
  String capitalize() {
    return "${this[0].toUpperCase()}${substring(1)}";
  }
}
