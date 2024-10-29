import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';
import 'package:uuid/uuid.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import '../utils/text_utils.dart';

class Editor extends StatefulWidget {
  final String projectId;
  final String? chapterId;

  const Editor({Key? key, required this.projectId, this.chapterId})
      : super(key: key);

  @override
  State<Editor> createState() => _EditorState();
}

class _EditorState extends State<Editor> {
  dynamic _selectedChapter;
  final TextEditingController _chapterTitleController = TextEditingController();
  final TextEditingController _chapterContentController =
      TextEditingController();
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchChapters();
    if (widget.chapterId != null) {
      _loadChapter(widget.chapterId!);
    }
  }

  Future<void> _fetchChapters() async {
    final appState = Provider.of<AppState>(context, listen: false);
    setState(() {
      _error = null;
    });

    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/chapters?project_id=${widget.projectId}'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final jsonResponse = json.decode(utf8.decode(response.bodyBytes));
        final List<dynamic> chapters = jsonResponse['chapters'];
        appState.setChapters(chapters);
      } else {
        final errorMessage = 'Error fetching chapters: ${response.statusCode}';
        print(errorMessage);
        setState(() {
          _error = errorMessage;
        });
      }
    } catch (error) {
      final errorMessage = 'Error fetching chapters: $error';
      print(errorMessage);
      setState(() {
        _error = errorMessage;
      });
    }
  }

  Future<void> _loadChapter(String chapterId) async {
    final appState = Provider.of<AppState>(context, listen: false);
    final chapter = appState.chapters
        .firstWhere((c) => c['id'] == chapterId, orElse: () => null);
    if (chapter != null) {
      setState(() {
        _selectedChapter = chapter;
        _chapterTitleController.text = chapter['title'];
        _chapterContentController.text = chapter['content'];
      });
    } else {
      // If the chapter is not in the state, fetch it from the API
      try {
        final headers = await getAuthHeaders();
        final response = await http.get(
          Uri.parse(
              '$apiUrl/chapters/$chapterId?project_id=${widget.projectId}'),
          headers: headers,
        );
        if (response.statusCode == 200) {
          final chapter = json.decode(utf8.decode(response.bodyBytes));
          setState(() {
            _selectedChapter = chapter;
            _chapterTitleController.text = chapter['title'];
            _chapterContentController.text = chapter['content'];
          });
        } else {
          Fluttertoast.showToast(msg: 'Error loading chapter');
        }
      } catch (error) {
        print('Error loading chapter: $error');
        Fluttertoast.showToast(msg: 'Error loading chapter');
      }
    }
  }

  Future<void> _handleChapterClick(dynamic chapter) async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse(
            '$apiUrl/chapters/${chapter['id']}?project_id=${widget.projectId}'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final fetchedChapter = json.decode(utf8.decode(response.bodyBytes));
        setState(() {
          _selectedChapter = fetchedChapter;
          _chapterTitleController.text = fetchedChapter['title'];
          _chapterContentController.text = fetchedChapter['content'];
          _error = null;
        });
      } else {
        print('Error loading chapter: ${response.statusCode}');
        Fluttertoast.showToast(msg: 'Error loading chapter');
      }
    } catch (error) {
      print('Error loading chapter: $error');
      Fluttertoast.showToast(msg: 'Error loading chapter');
    }
  }

  void _handleCreateChapter() {
    setState(() {
      _selectedChapter = null;
      _chapterTitleController.clear();
      _chapterContentController.clear();
      _error = null;
    });
  }

  Future<void> _handleDeleteChapter(String chapterId) async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.delete(
        Uri.parse('$apiUrl/chapters/$chapterId?project_id=${widget.projectId}'),
        headers: headers,
      );
      if (response.statusCode == 200) {
        // Remove from state first
        Provider.of<AppState>(context, listen: false).removeChapter(chapterId);
        setState(() {
          _selectedChapter = null;
        });
        Fluttertoast.showToast(msg: 'Chapter deleted successfully');
        // Add this line to refresh chapters from server
        await Provider.of<AppState>(context, listen: false)
            .fetchChapters(widget.projectId);
      } else {
        final jsonResponse = json.decode(response.body);
        final errorMessage = jsonResponse['error'] ?? 'Error deleting chapter';
        Fluttertoast.showToast(msg: errorMessage);
      }
    } catch (error) {
      print('Error deleting chapter: $error');
      Fluttertoast.showToast(msg: 'Error deleting chapter');
    }
  }

  Future<void> _handleSaveChapter() async {
    if (_chapterTitleController.text.isEmpty) {
      setState(() {
        _error = 'Chapter title is required.';
      });
      return;
    }

    final headers = await getAuthHeaders();
    final chapterId =
        _selectedChapter != null ? _selectedChapter['id'] : const Uuid().v4();

    try {
      final requestBody = {
        'title': _chapterTitleController.text,
        'content': _chapterContentController.text,
        'project_id': widget.projectId,
      };

      http.Response response;
      if (_selectedChapter != null) {
        // Update existing chapter
        response = await http.put(
          Uri.parse(
              '$apiUrl/chapters/$chapterId?project_id=${widget.projectId}'),
          headers: headers,
          body: json.encode(requestBody),
        );
      } else {
        // Create new chapter
        response = await http.post(
          Uri.parse('$apiUrl/chapters?project_id=${widget.projectId}'),
          headers: headers,
          body: utf8.encode(json.encode(requestBody)),
        );
      }
      final jsonResponse = json.decode(utf8.decode(response.bodyBytes));
      if ((response.statusCode == 200 || response.statusCode == 201) &&
          !jsonResponse.containsKey('error')) {
        final updatedChapter = {
          'id': chapterId,
          ...requestBody,
        };
        if (_selectedChapter != null) {
          Provider.of<AppState>(context, listen: false)
              .updateChapter(updatedChapter);
        } else {
          Provider.of<AppState>(context, listen: false)
              .addChapter(updatedChapter);
        }
        setState(() {
          _error = null;
          _selectedChapter = updatedChapter;
        });
        if (response.statusCode == 200) {
          Fluttertoast.showToast(msg: 'Chapter updated successfully');
        } else {
          Fluttertoast.showToast(msg: 'Chapter created successfully');
        }
        _fetchChapters();
      } else {
        final errorMessage = jsonResponse['error'] ?? 'Error saving chapter';
        Fluttertoast.showToast(msg: errorMessage);
        setState(() {
          _error = errorMessage;
        });
      }
    } catch (error) {
      print('Error saving chapter: $error');
      setState(() {
        _error = 'Error saving chapter. Please try again later.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        return Container(
          padding: const EdgeInsets.all(24),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Chapters sidebar
              SizedBox(
                width: 300,
                child: Card(
                  elevation: 4,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _buildChapterHeader(),
                      _buildChapterList(appState),
                      _buildCreateChapterButton(),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 24),
              // Editor main content
              Expanded(
                child: Card(
                  elevation: 4,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _buildEditorHeader(),
                      _buildEditorContent(),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildChapterHeader() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).dividerColor,
          ),
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.book,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(width: 8),
          Text(
            'Chapters',
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ],
      ),
    );
  }

  Widget _buildChapterList(AppState appState) {
    if (_error != null) {
      return _buildErrorState();
    }

    return Expanded(
      child: ListView.builder(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: appState.chapters.length,
        itemBuilder: (context, index) {
          final chapter = appState.chapters[index];
          final isSelected = _selectedChapter != null &&
              _selectedChapter['id'] == chapter['id'];

          return ListTile(
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 16,
              vertical: 4,
            ),
            title: Text(
              chapter['title'],
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            subtitle: Text(
              '${getWordCount(chapter['content'])} words',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            leading: Icon(
              Icons.article,
              color: isSelected
                  ? Theme.of(context).colorScheme.primary
                  : Theme.of(context).colorScheme.onSurface.withOpacity(0.5),
            ),
            trailing: IconButton(
              icon: Icon(
                Icons.delete,
                color: Theme.of(context).colorScheme.error,
              ),
              onPressed: () => _showDeleteDialog(chapter['id']),
            ),
            selected: isSelected,
            selectedTileColor: Theme.of(context).colorScheme.primaryContainer,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
            ),
            onTap: () => _handleChapterClick(chapter),
          );
        },
      ),
    );
  }

  Widget _buildCreateChapterButton() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: ElevatedButton.icon(
        onPressed: _handleCreateChapter,
        icon: const Icon(Icons.add),
        label: const Text('New Chapter'),
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.all(16),
        ),
      ),
    );
  }

  Widget _buildEditorHeader() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).dividerColor,
          ),
        ),
      ),
      child: Row(
        children: [
          Icon(
            _selectedChapter != null ? Icons.edit : Icons.add_circle,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(width: 8),
          Text(
            _selectedChapter != null ? 'Edit Chapter' : 'Create New Chapter',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const Spacer(),
          ElevatedButton.icon(
            onPressed: _handleSaveChapter,
            icon: const Icon(Icons.save),
            label: Text(_selectedChapter != null ? 'Save' : 'Create'),
          ),
        ],
      ),
    );
  }

  Widget _buildEditorContent() {
    return Expanded(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Card(
                  color: Theme.of(context).colorScheme.errorContainer,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        Icon(
                          Icons.error_outline,
                          color: Theme.of(context).colorScheme.error,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            _error!,
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.error,
                            ),
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.close),
                          onPressed: () => setState(() => _error = null),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            TextField(
              controller: _chapterTitleController,
              decoration: InputDecoration(
                labelText: 'Chapter Title',
                hintText: 'Enter chapter title...',
                prefixIcon: const Icon(Icons.title),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: TextField(
                controller: _chapterContentController,
                maxLines: null,
                expands: true,
                textAlignVertical: TextAlignVertical.top,
                decoration: InputDecoration(
                  labelText: 'Chapter Content',
                  hintText: 'Start writing your chapter...',
                  alignLabelWithHint: true,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showDeleteDialog(String chapterId) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Row(
            children: [
              Icon(Icons.warning, color: Theme.of(context).colorScheme.error),
              const SizedBox(width: 8),
              const Text('Delete Chapter'),
            ],
          ),
          content: const Text(
            'Are you sure you want to delete this chapter? This action cannot be undone.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Cancel'),
            ),
            ElevatedButton.icon(
              icon: const Icon(Icons.delete),
              label: const Text('Delete'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Theme.of(context).colorScheme.error,
              ),
              onPressed: () {
                Navigator.of(context).pop();
                _handleDeleteChapter(chapterId);
              },
            ),
          ],
        );
      },
    );
  }

  Widget _buildErrorState() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline,
                color: Theme.of(context).colorScheme.error, size: 48),
            const SizedBox(height: 16),
            Text(_error ?? 'An error occurred',
                style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ],
        ),
      ),
    );
  }
}
