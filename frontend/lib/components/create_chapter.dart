import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/constants.dart';
import '../providers/preset_provider.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';

class CreateChapter extends StatefulWidget {
  final String projectId;
  final bool readOnly;
  final bool showAppBar;

  const CreateChapter({
    Key? key,
    required this.projectId,
    this.readOnly = false,
    this.showAppBar = true,
  }) : super(key: key);

  @override
  State<CreateChapter> createState() => _CreateChapterState();
}

class _CreateChapterState extends State<CreateChapter> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _plotController = TextEditingController();
  final TextEditingController _writingStyleController = TextEditingController();
  final TextEditingController _styleGuideController = TextEditingController();
  final TextEditingController _wordCountController = TextEditingController();
  final TextEditingController _additionalInstructionsController =
      TextEditingController();
  final TextEditingController _newPresetNameController =
      TextEditingController();
  late final PresetProvider _presetProvider;

  int _numChapters = 1;
  String _currentChapterContent = '';
  List<String> _generatedChapterIds = [];
  int _displayedChapterIndex = 0;

  @override
  void initState() {
    super.initState();
    final appState = Provider.of<AppState>(context, listen: false);
    final presetProvider = Provider.of<PresetProvider>(context, listen: false);

    // Set project ID for presets
    presetProvider.setProjectId(widget.projectId);

    // Initialize controllers with saved state
    _plotController.text = appState.chapterCreationState['plot'] ?? '';
    _writingStyleController.text =
        appState.chapterCreationState['writingStyle'] ?? '';
    _styleGuideController.text =
        appState.chapterCreationState['styleGuide'] ?? '';
    _wordCountController.text =
        appState.chapterCreationState['wordCount'] ?? '';
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
    _wordCountController.addListener(() {
      appState.updateChapterCreationField(
          'wordCount', _wordCountController.text);
    });
    _additionalInstructionsController.addListener(() {
      appState.updateChapterCreationField(
          'additionalInstructions', _additionalInstructionsController.text);
    });

    _presetProvider = Provider.of<PresetProvider>(context, listen: false);
    _updateFieldsFromPreset(_presetProvider.currentPreset);
    _presetProvider.addListener(_onPresetChanged);

    // Fetch presets when the widget is initialized
    WidgetsBinding.instance.addPostFrameCallback((timeStamp) {
      _presetProvider.fetchPresets();
    });
  }

  @override
  void dispose() {
    _presetProvider.removeListener(_onPresetChanged);
    _plotController.dispose();
    _writingStyleController.dispose();
    _styleGuideController.dispose();
    _wordCountController.dispose();
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
        _wordCountController.text = preset['wordCount']?.toString() ?? '';
        _additionalInstructionsController.text =
            preset['additionalInstructions'] ?? '';
      });
    }
  }

  Future<void> _handleSavePreset() async {
    final presetProvider = Provider.of<PresetProvider>(context, listen: false);
    final scaffoldMessenger = ScaffoldMessenger.of(context);
    final newPresetName = _newPresetNameController.text;

    if (newPresetName.isEmpty) {
      scaffoldMessenger.showSnackBar(
        const SnackBar(content: Text('Please enter a preset name')),
      );
      return;
    }

    final presetData = {
      'numChapters': _numChapters,
      'plot': _plotController.text,
      'writingStyle': _writingStyleController.text,
      'styleGuide': _styleGuideController.text,
      'wordCount': int.tryParse(_wordCountController.text) ?? 1000,
      'additionalInstructions': _additionalInstructionsController.text,
      'project_id': widget.projectId,
    };

    try {
      await presetProvider.savePreset(newPresetName, presetData);
      if (!context.mounted) return;
      scaffoldMessenger.showSnackBar(
        const SnackBar(content: Text('Preset saved successfully')),
      );
      _newPresetNameController.clear();
      await _presetProvider.fetchPresets();
    } catch (e) {
      if (!context.mounted) return;
      scaffoldMessenger.showSnackBar(
        SnackBar(content: Text('Error saving preset: ${e.toString()}')),
      );
    }
  }

  Future<void> _handleSubmit(BuildContext context) async {
    final appState = Provider.of<AppState>(context, listen: false);
    final scaffoldMessenger = ScaffoldMessenger.of(context);

    if (_formKey.currentState!.validate()) {
      setState(() {
        _generatedChapterIds = [];
        _currentChapterContent = '';
        _displayedChapterIndex = 0;
      });

      final plot = _plotController.text;
      final numChapters = _numChapters;
      final writingStyle = _writingStyleController.text;

      final instructionsMap = {
        'styleGuide': _styleGuideController.text,
        'additionalInstructions': _additionalInstructionsController.text,
        'wordCount': int.tryParse(_wordCountController.text) ?? 1000,
      };

      await appState.generateChapter(
        projectId: widget.projectId,
        description: plot,
        numChapters: numChapters,
        writingStyle: writingStyle,
        instructions: instructionsMap,
        onSuccess: (List<dynamic> successfulChaptersData) async {
          final chapterIds = successfulChaptersData
              .map((chapterData) => chapterData['id'] as String?)
              .where((id) => id != null)
              .cast<String>()
              .toList();

          if (!mounted) return;

          if (chapterIds.isNotEmpty) {
            setState(() {
              _generatedChapterIds = chapterIds;
              _displayedChapterIndex = 0;
            });
            await _fetchChapterContent(chapterIds[0]);

            scaffoldMessenger.showSnackBar(
              const SnackBar(content: Text('Chapters generated successfully')),
            );
          } else {
            _showError(scaffoldMessenger,
                'No valid chapter data received after generation.');
          }
        },
        onError: (String error) {
          if (!mounted) return;
          _showError(scaffoldMessenger, 'Error generating chapters: $error');
        },
      );
    }
  }

  void _showError(ScaffoldMessengerState messenger, String message) {
    messenger.showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
      ),
    );
  }

  Future<void> _fetchChapterContent(String chapterId) async {
    final scaffoldMessenger = ScaffoldMessenger.of(context);

    try {
      final response = await http.get(
        Uri.parse('$apiUrl/projects/${widget.projectId}/chapters/$chapterId'),
      );

      if (response.statusCode == 200) {
        if (!mounted) return;
        final chapterData = json.decode(utf8.decode(response.bodyBytes));
        setState(() {
          _currentChapterContent =
              chapterData['content'] ?? 'No content found.';
        });
      } else {
        _showError(scaffoldMessenger,
            'Error fetching chapter content: ${response.statusCode}');
      }
    } catch (error) {
      _showError(scaffoldMessenger, 'Error fetching chapter content: $error');
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

  void _handlePresetChange(String? newValue) {
    final presetProvider = Provider.of<PresetProvider>(context, listen: false);
    if (newValue == null) {
      presetProvider.loadPreset("select a preset");
      setState(() {
        _numChapters = 1;
        _plotController.text = '';
        _writingStyleController.text = '';
        _styleGuideController.text = '';
        _wordCountController.text = '1000';
        _additionalInstructionsController.text = '';
      });
    } else {
      presetProvider.loadPreset(newValue);
    }
  }

  Future<void> _handleDeletePreset(String presetName) async {
    final presetProvider = Provider.of<PresetProvider>(context, listen: false);
    final scaffoldMessenger = ScaffoldMessenger.of(context);
    try {
      await presetProvider.deletePreset(presetName);
      if (!context.mounted) return;
      scaffoldMessenger.showSnackBar(
        const SnackBar(content: Text('Preset deleted successfully')),
      );
      // Reset fields after deleting preset
      _numChapters = 1;
      _plotController.clear();
      _writingStyleController.clear();
      _styleGuideController.clear();
      _wordCountController.clear();
      _additionalInstructionsController.clear();
      await _presetProvider.fetchPresets();
    } catch (error) {
      if (!context.mounted) return;
      scaffoldMessenger.showSnackBar(
        SnackBar(content: Text('Error deleting preset: ${error.toString()}')),
      );
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
                _handleDeletePreset(presetProvider.selectedPreset!);
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
              'Generated Chapter',
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

  Future<bool> _onWillPop() async {
    final appState = Provider.of<AppState>(context, listen: false);
    if (appState.chapterCreationState['isGenerating']) {
      final shouldLeave = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Generation in Progress'),
          content: const Text(
              'Chapter generation is still in progress. Are you sure you want to leave?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('Stay'),
            ),
            TextButton(
              onPressed: () {
                appState.cancelChapterGeneration();
                Navigator.of(context).pop(true);
              },
              child: const Text('Leave'),
            ),
          ],
        ),
      );
      return shouldLeave ?? false;
    }
    return true;
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        final isGenerating =
            appState.chapterCreationState['isGenerating'] ?? false;
        final generationProgress =
            appState.chapterCreationState['progress'] as double? ?? 0.0;
        final currentChapterNum =
            appState.chapterCreationState['currentChapter'] as int? ?? 0;
        final totalChaptersToGen = _numChapters;

        Widget content = Container(
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
                                  controller: _wordCountController,
                                  decoration: const InputDecoration(
                                    labelText: 'Word Count Target',
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
                                if (isGenerating)
                                  Column(
                                    children: [
                                      LinearProgressIndicator(
                                        value: totalChaptersToGen > 1
                                            ? generationProgress
                                            : null,
                                        backgroundColor: const Color(0xFF343a40),
                                        valueColor:
                                            const AlwaysStoppedAnimation<Color>(
                                                Color(0xFF007bff)),
                                      ),
                                      const SizedBox(height: 10),
                                      Text(
                                        totalChaptersToGen > 1
                                            ? 'Generating chapter ${currentChapterNum + 1} of $totalChaptersToGen...'
                                            : 'Generating chapter...',
                                        style:
                                            const TextStyle(color: Color(0xFFf8f9fa)),
                                      ),
                                    ],
                                  )
                                else
                                  ElevatedButton(
                                    onPressed: isGenerating
                                        ? null
                                        : () => _handleSubmit(context),
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: const Color(0xFF007bff),
                                      padding: const EdgeInsets.symmetric(
                                          horizontal: 20, vertical: 10),
                                      textStyle: const TextStyle(fontSize: 18),
                                    ),
                                    child: Text(isGenerating
                                        ? 'Generation in progress...'
                                        : 'Generate Chapter'),
                                  )
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

        if (widget.showAppBar) {
          return PopScope(
            canPop: false,
            onPopInvokedWithResult: (didPop, result) {
              if (!didPop) {
                _onWillPop().then((shouldPop) {
                  if (shouldPop && context.mounted) {
                    Navigator.of(context).pop();
                  }
                });
              }
            },
            child: Scaffold(
              appBar: AppBar(
                elevation: 0,
                automaticallyImplyLeading: false,
                title: Row(
                  children: [
                    Icon(Icons.create_new_folder,
                        color: Theme.of(context).colorScheme.primary),
                    const SizedBox(width: 12),
                    const Text('Create New Chapter'),
                  ],
                ),
              ),
              body: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      Theme.of(context).colorScheme.surface,
                      Theme.of(context).colorScheme.surface.withOpacity(0.8),
                    ],
                  ),
                ),
                child: content,
              ),
            ),
          );
        }

        return content;
      },
    );
  }
}
