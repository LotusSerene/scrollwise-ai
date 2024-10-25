import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';

class CodexGeneration extends StatefulWidget {
  final String projectId;

  const CodexGeneration({Key? key, required this.projectId}) : super(key: key);

  @override
  State<CodexGeneration> createState() => _CodexGenerationState();
}

class _CodexGenerationState extends State<CodexGeneration> {
  final _formKey = GlobalKey<FormState>();
  late AppState _appState;

  String _selectedType =
      'worldbuilding'; // This should match one of the values in _types
  String? _selectedSubtype;
  String _description = '';
  dynamic _generatedItem;

  final List<String> _types = ['worldbuilding', 'character', 'item', 'lore'];
  final Map<String, List<String>> _subtypes = {
    'worldbuilding': ['history', 'culture', 'geography'],
    'character': [],
    'item': [],
    'lore': [],
  };

  @override
  void initState() {
    super.initState();
    _appState = Provider.of<AppState>(context, listen: false);

    // Initialize with saved state if it exists
    final savedState = _appState.getGenerationState('codex');
    if (savedState != null) {
      // Make sure the saved type exists in _types before setting it
      if (_types.contains(savedState.type)) {
        _selectedType = savedState.type;
      }
      _selectedSubtype = savedState.subtype;
      _description = savedState.description ?? '';
      _generatedItem = savedState.lastGeneratedItem;
    }
  }

  Future<void> _handleSubmit() async {
    if (_formKey.currentState!.validate()) {
      _appState.setGenerationState(
        'codex',
        subtype: _selectedSubtype,
        description: _description,
        isGenerating: true,
      );

      try {
        final headers = {...await getAuthHeaders()};

        final requestBody = {
          'codex_type': _selectedType,
          'subtype': _selectedSubtype,
          'description': _description,
        };

        final response = await http.post(
          Uri.parse('$apiUrl/codex/generate?project_id=${widget.projectId}'),
          headers: headers,
          body: utf8.encode(json.encode(requestBody)),
        );

        if (response.statusCode == 200) {
          final data = json.decode(utf8.decode(response.bodyBytes));
          _appState.setGenerationState(
            'codex',
            lastGeneratedItem: data['item'],
            isGenerating: false,
          );
          Fluttertoast.showToast(msg: 'Codex item generated successfully');
        } else {
          _appState.setGenerationState('codex', isGenerating: false);
          Fluttertoast.showToast(
              msg: 'Error generating codex item: ${response.body}');
        }
      } catch (error) {
        _appState.setGenerationState('codex', isGenerating: false);
        print('Error generating codex item: $error');
        Fluttertoast.showToast(msg: 'Error generating codex item: $error');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        final generationState = appState.getGenerationState('codex');
        final isGenerating = generationState?.isGenerating ?? false;
        final generatedItem = generationState?.lastGeneratedItem;

        return Padding(
          padding: const EdgeInsets.all(24),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Generation Form
              Expanded(
                flex: 1,
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
              const SizedBox(width: 24),
              // Generated Result
              if (generatedItem != null)
                Expanded(
                  flex: 1,
                  child: _buildGeneratedResult(generatedItem),
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
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildTypeDropdown(),
          const SizedBox(height: 16),
          if (_selectedType == 'worldbuilding') ...[
            _buildSubtypeDropdown(),
            const SizedBox(height: 16),
          ],
          _buildDescriptionField(),
          const SizedBox(height: 24),
          _buildGenerateButton(isGenerating),
        ],
      ),
    );
  }

  Widget _buildTypeDropdown() {
    return DropdownButtonFormField<String>(
      value: _selectedType,
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
          key: ValueKey(type), // Add a unique key for each item
          child: Text(type.capitalize()),
        );
      }).toList(),
      onChanged: (value) {
        setState(() {
          _selectedType = value!;
          _selectedSubtype = null;
        });
      },
    );
  }

  Widget _buildSubtypeDropdown() {
    return DropdownButtonFormField<String>(
      value: _selectedSubtype,
      decoration: InputDecoration(
        labelText: 'Subtype',
        prefixIcon: const Icon(Icons.subdirectory_arrow_right),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
      items: _subtypes[_selectedType]!.map((subtype) {
        return DropdownMenuItem<String>(
          value: subtype,
          child: Text(subtype.capitalize()),
        );
      }).toList(),
      onChanged: (value) {
        setState(() {
          _selectedSubtype = value;
        });
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
      onChanged: (value) {
        setState(() {
          _description = value;
        });
      },
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
                    _appState.resetGenerationState('codex');
                  },
                  icon: const Icon(Icons.refresh),
                  label: const Text('Generate Another'),
                ),
                const SizedBox(width: 16),
                ElevatedButton.icon(
                  onPressed: () {
                    // Add to codex implementation
                  },
                  icon: const Icon(Icons.add),
                  label: const Text('Add to Codex'),
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
