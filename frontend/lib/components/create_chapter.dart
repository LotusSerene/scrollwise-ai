import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/notifications.dart';
import '../utils/auth.dart';
import '../utils/constants.dart';
import '../providers/preset_provider.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';

class CreateChapter extends StatefulWidget {
  final String projectId;
  final bool readOnly;

  const CreateChapter({
    Key? key,
    required this.projectId,
    this.readOnly = false,
  }) : super(key: key);

  @override
  State<CreateChapter> createState() => _CreateChapterState();
}

class _CreateChapterState extends State<CreateChapter> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _plotController = TextEditingController();
  final TextEditingController _writingStyleController = TextEditingController();
  final TextEditingController _styleGuideController = TextEditingController();
  final TextEditingController _minWordCountController = TextEditingController();
  final TextEditingController _additionalInstructionsController =
      TextEditingController();
  final TextEditingController _newPresetNameController =
      TextEditingController();
  late final PresetProvider _presetProvider;

  int _numChapters = 1;
  bool _isGenerating = false;
  String _currentChapterContent = '';
  List<String> _generatedChapterIds = [];
  int _displayedChapterIndex = 0;

  @override
  void initState() {
    super.initState();
    final appState = Provider.of<AppState>(context, listen: false);

    // Initialize controllers with saved state
    _plotController.text = appState.chapterCreationState['plot'] ?? '';
    _writingStyleController.text =
        appState.chapterCreationState['writingStyle'] ?? '';
    _styleGuideController.text =
        appState.chapterCreationState['styleGuide'] ?? '';
    _minWordCountController.text =
        appState.chapterCreationState['minWordCount'] ?? '';
    _additionalInstructionsController.text =
        appState.chapterCreationState['additionalInstructions'] ?? '';

    // Add listeners to update state when text changes
    _plotController.addListener(() {
      appState.updateChapterCreationField('plot', _plotController.text);
    });
    _writingStyleController.addListener(() {
      appState.updateChapterCreationField(
          'writingStyle', _writingStyleController.text);
    });
    _styleGuideController.addListener(() {
      appState.updateChapterCreationField(
          'styleGuide', _styleGuideController.text);
    });
    _minWordCountController.addListener(() {
      appState.updateChapterCreationField(
          'minWordCount', _minWordCountController.text);
    });
    _additionalInstructionsController.addListener(() {
      appState.updateChapterCreationField(
          'additionalInstructions', _additionalInstructionsController.text);
    });

    _presetProvider = Provider.of<PresetProvider>(context, listen: false);
    _updateFieldsFromPreset(_presetProvider.currentPreset);
    _presetProvider.addListener(_onPresetChanged);

    // Fetch presets when the widget is initialized
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _presetProvider.fetchPresets(widget.projectId);
    });
  }

  @override
  void dispose() {
    _presetProvider.removeListener(_onPresetChanged);
    _plotController.dispose();
    _writingStyleController.dispose();
    _styleGuideController.dispose();
    _minWordCountController.dispose();
    _additionalInstructionsController.dispose();
    _newPresetNameController.dispose();
    super.dispose();
  }

  void _onPresetChanged() {
    _updateFieldsFromPreset(_presetProvider.currentPreset);
  }

  void _updateFieldsFromPreset(Map<String, dynamic>? preset) {
    if (preset != null) {
      setState(() {
        _numChapters = preset['numChapters'] ?? 1;
        _plotController.text = preset['plot'] ?? '';
        _writingStyleController.text = preset['writingStyle'] ?? '';
        _styleGuideController.text = preset['styleGuide'] ?? '';
        _minWordCountController.text = preset['minWordCount']?.toString() ?? '';
        _additionalInstructionsController.text =
            preset['additionalInstructions'] ?? '';
      });
    }
  }

  Future<void> _handleSavePreset() async {
    final presetProvider = Provider.of<PresetProvider>(context, listen: false);
    final newPresetName = _newPresetNameController.text;

    if (newPresetName.isEmpty) {
      AppNotification.show(context, 'Please enter a preset name');
      return;
    }

    final presetData = {
      'numChapters': _numChapters,
      'plot': _plotController.text,
      'writingStyle': _writingStyleController.text,
      'styleGuide': _styleGuideController.text,
      'minWordCount': int.tryParse(_minWordCountController.text) ?? 1000,
      'additionalInstructions': _additionalInstructionsController.text,
    };

    try {
      await presetProvider.savePreset(
          newPresetName, presetData, widget.projectId);
      AppNotification.show(context, 'Preset saved successfully');
      _newPresetNameController.clear();
    } catch (e) {
      AppNotification.show(context, 'Error saving preset: $e');
    }
  }

  Future<void> _handleSubmit(BuildContext context) async {
    final appState = Provider.of<AppState>(context, listen: false);

    if (_formKey.currentState!.validate()) {
      appState.updateGenerationProgress(
        isGenerating: true,
        currentChapter: 0,
        progress: 0.0,
        streamedContent: '',
        generatedChapters: [],
      );

      try {
        final headers = {
          ...await getAuthHeaders(),
          'Content-Type': 'application/json',
        };

        final requestBody = {
          'numChapters': _numChapters,
          'plot': _plotController.text,
          'writingStyle': _writingStyleController.text,
          'instructions': {
            'styleGuide': _styleGuideController.text,
            'minWordCount': int.tryParse(_minWordCountController.text) ?? 1000,
            'additionalInstructions': _additionalInstructionsController.text,
          },
          'project_id': widget.projectId,
        };

        final response = await http.post(
          Uri.parse('$apiUrl/chapters/generate?project_id=${widget.projectId}'),
          headers: headers,
          body: utf8.encode(json.encode(requestBody)),
        );

        if (response.statusCode == 200) {
          final responseData = json.decode(response.body);

          List<String> chapterIds = [];

          if (responseData['generated_chapter_ids'] != null) {
            chapterIds =
                List<String>.from(responseData['generated_chapter_ids']);
          } else if (responseData['generated_chapters'] != null) {
            chapterIds = List<String>.from(
                (responseData['generated_chapters'] as List)
                    .map((chapter) => chapter['id']));
          }

          if (chapterIds.isNotEmpty) {
            setState(() {
              _generatedChapterIds = chapterIds;
              _displayedChapterIndex = 0;
            });

            await _fetchChapterContent(chapterIds[0]);

            appState.completeChapterGeneration();
            AppNotification.show(context, 'Chapters generated successfully');
          } else {
            throw Exception('No chapter IDs received from server');
          }
        } else {
          throw Exception('Error ${response.statusCode}: ${response.body}');
        }
      } catch (error) {
        appState.cancelChapterGeneration();
        AppNotification.show(context, 'Error generating chapters: $error');
      }
    }
  }

  Future<void> _fetchChapterContent(String chapterId) async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/chapters/$chapterId?project_id=${widget.projectId}'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final chapterData = json.decode(response.body);
        setState(() {
          _currentChapterContent = chapterData['content'];
        });
      } else {
        AppNotification.show(context, 'Error fetching chapter content');
      }
    } catch (error) {
      AppNotification.show(context, 'Error fetching chapter content');
    }
  }

  void _navigateChapters(int direction) async {
    int newIndex = _displayedChapterIndex + direction;
    if (newIndex >= 0 && newIndex < _generatedChapterIds.length) {
      setState(() {
        _displayedChapterIndex = newIndex;
      });
      await _fetchChapterContent(_generatedChapterIds[newIndex]);
    }
  }

  Future<void> _handleCancel() async {
    final appState = Provider.of<AppState>(context, listen: false);
    try {
      final response = await http.post(
        Uri.parse('$apiUrl/chapters/cancel?project_id=${widget.projectId}'),
        headers: await getAuthHeaders(),
      );

      if (response.statusCode == 200) {
        appState.cancelChapterGeneration();
        AppNotification.show(context, 'Chapter generation cancelled');
      } else {
        AppNotification.show(context, 'Failed to cancel chapter generation');
      }
    } catch (error) {
      print('Error cancelling chapter generation: $error');
      AppNotification.show(context, 'Error cancelling chapter generation');
    }
  }

  void _handlePresetChange(String? newValue) {
    final presetProvider = Provider.of<PresetProvider>(context, listen: false);
    if (newValue == null) {
      presetProvider.clearSelectedPreset();
      setState(() {
        _numChapters = 1;
        _plotController.text = '';
        _writingStyleController.text = '';
        _styleGuideController.text = '';
        _minWordCountController.text = '1000';
        _additionalInstructionsController.text = '';
      });
    } else {
      presetProvider.loadPreset(newValue, widget.projectId);
    }
  }

  Future<void> _handleDeletePreset(String presetName) async {
    final presetProvider = Provider.of<PresetProvider>(context, listen: false);
    try {
      await presetProvider.deletePreset(presetName, widget.projectId);
      AppNotification.show(context, 'Preset deleted successfully');
    } catch (error) {
      AppNotification.show(
          context, 'Error deleting preset: ${error.toString()}');
    }
  }

  Widget _buildPresetDropdown(PresetProvider presetProvider) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Theme.of(context).dividerColor),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          isExpanded: true,
          value: presetProvider.selectedPreset,
          hint: Text('Select a preset',
              style: Theme.of(context).textTheme.bodyLarge),
          icon: const Icon(Icons.arrow_drop_down),
          borderRadius: BorderRadius.circular(12),
          items: [
            const DropdownMenuItem<String>(
              value: null,
              child: Text('No Preset'),
            ),
            ...presetProvider.presets.map((String preset) {
              return DropdownMenuItem<String>(
                value: preset,
                child: Row(
                  children: [
                    const Icon(Icons.bookmark_outline),
                    const SizedBox(width: 8),
                    Expanded(child: Text(preset)),
                  ],
                ),
              );
            }).toList(),
          ],
          onChanged: _handlePresetChange,
        ),
      ),
    );
  }

  Widget _buildPresetActions(PresetProvider presetProvider) {
    return Row(
      children: [
        if (presetProvider.selectedPreset != null)
          IconButton(
            icon: const Icon(Icons.delete_outline),
            tooltip: 'Delete Preset',
            onPressed: () => _showDeletePresetDialog(presetProvider),
            color: Theme.of(context).colorScheme.error,
          ),
        IconButton(
          icon: const Icon(Icons.save_outlined),
          tooltip: 'Save New Preset',
          onPressed: () => _showSavePresetDialog(),
          color: Theme.of(context).colorScheme.primary,
        ),
      ],
    );
  }

  void _showSavePresetDialog() {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Row(
            children: [
              Icon(Icons.save, color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 8),
              const Text('Save Preset'),
            ],
          ),
          content: TextField(
            controller: _newPresetNameController,
            decoration: InputDecoration(
              labelText: 'Preset Name',
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              prefixIcon: const Icon(Icons.bookmark_add_outlined),
            ),
            autofocus: true,
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton.icon(
              icon: const Icon(Icons.save),
              label: const Text('Save'),
              onPressed: () {
                Navigator.pop(context);
                _handleSavePreset();
              },
            ),
          ],
        );
      },
    );
  }

  void _showDeletePresetDialog(PresetProvider presetProvider) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Row(
            children: [
              Icon(Icons.warning, color: Theme.of(context).colorScheme.error),
              const SizedBox(width: 8),
              const Text('Delete Preset'),
            ],
          ),
          content: Text(
              'Are you sure you want to delete "${presetProvider.selectedPreset}"?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton.icon(
              icon: const Icon(Icons.delete),
              label: const Text('Delete'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Theme.of(context).colorScheme.error,
              ),
              onPressed: () {
                Navigator.pop(context);
                presetProvider.deletePreset(
                    presetProvider.selectedPreset!, widget.projectId);
              },
            ),
          ],
        );
      },
    );
  }

  Widget _buildGeneratedChaptersSection() {
    return Card(
      elevation: 4,
      margin: const EdgeInsets.only(top: 24),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          ListTile(
            title: Text(
              'Generated Chapter ${_displayedChapterIndex + 1}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (_generatedChapterIds.length > 1) ...[
                  IconButton(
                    icon: const Icon(Icons.arrow_back),
                    onPressed: _displayedChapterIndex > 0
                        ? () => _navigateChapters(-1)
                        : null,
                  ),
                  IconButton(
                    icon: const Icon(Icons.arrow_forward),
                    onPressed:
                        _displayedChapterIndex < _generatedChapterIds.length - 1
                            ? () => _navigateChapters(1)
                            : null,
                  ),
                ],
              ],
            ),
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Text(
                _currentChapterContent,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        final generationState = appState.chapterCreationState;
        _isGenerating = generationState['isGenerating'];

        return Container(
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
          child: LayoutBuilder(
            builder: (context, constraints) {
              return Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Flexible(
                    child: SingleChildScrollView(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Generate New Chapter',
                            style: TextStyle(
                              color: Color(0xFF007bff),
                              fontSize: 24,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 20),
                          const Text(
                            'Fill in the form below to generate a new chapter for your story. Provide as much detail as possible to get the best results.',
                            style: TextStyle(
                              color: Color(0xFFf8f9fa),
                              fontSize: 16,
                            ),
                          ),
                          const SizedBox(height: 20),
                          Consumer<PresetProvider>(
                            builder: (context, presetProvider, child) {
                              return Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    'Preset Settings:',
                                    style: TextStyle(
                                      color: Color(0xFFf8f9fa),
                                      fontSize: 16,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  const SizedBox(height: 10),
                                  Row(
                                    children: [
                                      Expanded(
                                        child: _buildPresetDropdown(
                                            presetProvider),
                                      ),
                                      const SizedBox(width: 10),
                                      _buildPresetActions(presetProvider),
                                    ],
                                  ),
                                ],
                              );
                            },
                          ),
                          const SizedBox(height: 20),
                          Form(
                            key: _formKey,
                            child: Column(
                              children: [
                                TextFormField(
                                  decoration: const InputDecoration(
                                    labelText: 'Number of Chapters',
                                    labelStyle:
                                        TextStyle(color: Color(0xFFf8f9fa)),
                                    enabledBorder: OutlineInputBorder(
                                      borderSide:
                                          BorderSide(color: Color(0xFFced4da)),
                                    ),
                                    focusedBorder: OutlineInputBorder(
                                      borderSide:
                                          BorderSide(color: Color(0xFF007bff)),
                                    ),
                                  ),
                                  style:
                                      const TextStyle(color: Color(0xFFf8f9fa)),
                                  keyboardType: TextInputType.number,
                                  initialValue: _numChapters.toString(),
                                  onChanged: (value) {
                                    setState(() {
                                      _numChapters = int.tryParse(value) ?? 1;
                                    });
                                  },
                                  validator: (value) {
                                    if (value == null || value.isEmpty) {
                                      return 'Please enter a number';
                                    }
                                    return null;
                                  },
                                ),
                                const SizedBox(height: 15),
                                TextFormField(
                                  controller: _plotController,
                                  decoration: const InputDecoration(
                                    labelText: 'Plot',
                                    alignLabelWithHint: true,
                                    labelStyle:
                                        TextStyle(color: Color(0xFFf8f9fa)),
                                    enabledBorder: OutlineInputBorder(
                                      borderSide:
                                          BorderSide(color: Color(0xFFced4da)),
                                    ),
                                    focusedBorder: OutlineInputBorder(
                                      borderSide:
                                          BorderSide(color: Color(0xFF007bff)),
                                    ),
                                  ),
                                  style:
                                      const TextStyle(color: Color(0xFFf8f9fa)),
                                  maxLines: null,
                                  minLines: 3,
                                ),
                                const SizedBox(height: 15),
                                TextFormField(
                                  controller: _writingStyleController,
                                  decoration: const InputDecoration(
                                    labelText: 'Writing Style',
                                    alignLabelWithHint: true,
                                    labelStyle:
                                        TextStyle(color: Color(0xFFf8f9fa)),
                                    enabledBorder: OutlineInputBorder(
                                      borderSide:
                                          BorderSide(color: Color(0xFFced4da)),
                                    ),
                                    focusedBorder: OutlineInputBorder(
                                      borderSide:
                                          BorderSide(color: Color(0xFF007bff)),
                                    ),
                                  ),
                                  style:
                                      const TextStyle(color: Color(0xFFf8f9fa)),
                                  maxLines: null,
                                  minLines: 2,
                                ),
                                const SizedBox(height: 15),
                                TextFormField(
                                  controller: _styleGuideController,
                                  decoration: const InputDecoration(
                                    labelText: 'Style Guide',
                                    alignLabelWithHint: true,
                                    labelStyle:
                                        TextStyle(color: Color(0xFFf8f9fa)),
                                    enabledBorder: OutlineInputBorder(
                                      borderSide:
                                          BorderSide(color: Color(0xFFced4da)),
                                    ),
                                    focusedBorder: OutlineInputBorder(
                                      borderSide:
                                          BorderSide(color: Color(0xFF007bff)),
                                    ),
                                  ),
                                  style:
                                      const TextStyle(color: Color(0xFFf8f9fa)),
                                  maxLines: null,
                                  minLines: 3,
                                ),
                                const SizedBox(height: 15),
                                TextFormField(
                                  controller: _minWordCountController,
                                  decoration: const InputDecoration(
                                    labelText: 'Minimum Word Count',
                                    labelStyle:
                                        TextStyle(color: Color(0xFFf8f9fa)),
                                    enabledBorder: OutlineInputBorder(
                                      borderSide:
                                          BorderSide(color: Color(0xFFced4da)),
                                    ),
                                    focusedBorder: OutlineInputBorder(
                                      borderSide:
                                          BorderSide(color: Color(0xFF007bff)),
                                    ),
                                  ),
                                  style:
                                      const TextStyle(color: Color(0xFFf8f9fa)),
                                  keyboardType: TextInputType.number,
                                  validator: (value) {
                                    if (value == null || value.isEmpty) {
                                      return 'Please enter a number';
                                    }
                                    return null;
                                  },
                                ),
                                const SizedBox(height: 15),
                                TextFormField(
                                  controller: _additionalInstructionsController,
                                  decoration: const InputDecoration(
                                    labelText: 'Additional Instructions',
                                    alignLabelWithHint: true,
                                    labelStyle:
                                        TextStyle(color: Color(0xFFf8f9fa)),
                                    enabledBorder: OutlineInputBorder(
                                      borderSide:
                                          BorderSide(color: Color(0xFFced4da)),
                                    ),
                                    focusedBorder: OutlineInputBorder(
                                      borderSide:
                                          BorderSide(color: Color(0xFF007bff)),
                                    ),
                                  ),
                                  style:
                                      const TextStyle(color: Color(0xFFf8f9fa)),
                                  maxLines: null,
                                  minLines: 3,
                                ),
                                const SizedBox(height: 20),
                                if (_isGenerating)
                                  Column(
                                    children: [
                                      const LinearProgressIndicator(
                                        value: 1,
                                        backgroundColor: Color(0xFF343a40),
                                        valueColor:
                                            AlwaysStoppedAnimation<Color>(
                                                Color(0xFF007bff)),
                                      ),
                                      const SizedBox(height: 10),
                                      const Text(
                                        'Generating chapter...',
                                        style:
                                            TextStyle(color: Color(0xFFf8f9fa)),
                                      ),
                                      const SizedBox(height: 10),
                                      ElevatedButton(
                                        onPressed: _handleCancel,
                                        style: ElevatedButton.styleFrom(
                                          backgroundColor: Colors.red,
                                          padding: const EdgeInsets.symmetric(
                                              horizontal: 20, vertical: 10),
                                          textStyle:
                                              const TextStyle(fontSize: 18),
                                        ),
                                        child: const Text('Cancel'),
                                      ),
                                    ],
                                  )
                                else
                                  ElevatedButton(
                                    onPressed: () => _handleSubmit(context),
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: const Color(0xFF007bff),
                                      padding: const EdgeInsets.symmetric(
                                          horizontal: 20, vertical: 10),
                                      textStyle: const TextStyle(fontSize: 18),
                                    ),
                                    child: const Text('Generate Chapter'),
                                  ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  if (_generatedChapterIds.isNotEmpty)
                    SizedBox(
                      height: constraints.maxHeight * 0.4,
                      child: _buildGeneratedChaptersSection(),
                    ),
                ],
              );
            },
          ),
        );
      },
    );
  }
}
