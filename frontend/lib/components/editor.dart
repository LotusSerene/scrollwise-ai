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
import 'package:file_picker/file_picker.dart';
import 'package:http_parser/http_parser.dart';

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

  // Add new state variables
  bool _mounted = true;
  bool _isLoading = false;
  final ScrollController _chapterListController = ScrollController();
  final int _itemsPerPage = 10;
  List<dynamic> _displayedChapters = [];
  bool _isLoadingMore = false;

  @override
  void initState() {
    super.initState();
    _chapterListController.addListener(_onScroll);
    _fetchChapters();
    if (widget.chapterId != null) {
      _loadChapter(widget.chapterId!);
    }
  }

  @override
  void dispose() {
    _mounted = false;
    _chapterListController.dispose();
    _chapterTitleController.dispose();
    _chapterContentController.dispose();
    super.dispose();
  }

  void _safeSetState(VoidCallback fn) {
    if (_mounted && mounted) {
      setState(fn);
    }
  }

  void _onScroll() {
    if (_chapterListController.position.pixels >=
        _chapterListController.position.maxScrollExtent * 0.8) {
      _loadMoreChapters();
    }
  }

  void _loadMoreChapters() {
    if (_isLoadingMore) return;

    final appState = Provider.of<AppState>(context, listen: false);
    final startIndex = _displayedChapters.length;
    if (startIndex >= appState.chapters.length) return;

    _safeSetState(() {
      _isLoadingMore = true;
    });

    Future.delayed(const Duration(milliseconds: 500), () {
      if (!_mounted) return;

      final newItems =
          appState.chapters.skip(startIndex).take(_itemsPerPage).toList();

      _safeSetState(() {
        _displayedChapters.addAll(newItems);
        _isLoadingMore = false;
      });
    });
  }

  Future<void> _fetchChapters() async {
    _safeSetState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/chapters?project_id=${widget.projectId}'),
        headers: headers,
      );

      if (!_mounted) return;

      if (response.statusCode == 200) {
        final jsonResponse = json.decode(utf8.decode(response.bodyBytes));
        final List<dynamic> chapters = jsonResponse['chapters'];
        Provider.of<AppState>(context, listen: false).setChapters(chapters);

        _safeSetState(() {
          _displayedChapters = chapters.take(_itemsPerPage).toList();
          _isLoading = false;
        });
      } else {
        _safeSetState(() {
          _error = 'Error fetching chapters: ${response.statusCode}';
          _isLoading = false;
        });
      }
    } catch (error) {
      if (!_mounted) return;
      _safeSetState(() {
        _error = 'Error fetching chapters: $error';
        _isLoading = false;
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

  Future<void> _importDocuments() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['txt', 'md', 'pdf', 'doc', 'docx'],
        allowMultiple: true,
        withData: true,
      );

      if (result != null) {
        for (var file in result.files) {
          if (file.bytes == null) {
            Fluttertoast.showToast(
                msg: 'Error: Could not read file ${file.name}');
            continue;
          }

          String content;
          final title = file.name
              .replaceAll(RegExp(r'\.[^/.]+$'), ''); // Remove extension

          // Handle text files directly
          if (file.extension?.toLowerCase() == 'txt' ||
              file.extension?.toLowerCase() == 'md') {
            content = utf8.decode(file.bytes!);
            await _createChapterFromContent(title, content);
          }
          // Handle other document types
          else {
            // Create multipart request for document processing
            final request = http.MultipartRequest(
              'POST',
              Uri.parse(
                  '$apiUrl/documents/extract?project_id=${widget.projectId}'),
            );

            request.headers.addAll(await getAuthHeaders());
            request.files.add(
              http.MultipartFile.fromBytes(
                'file',
                file.bytes!,
                filename: file.name,
                contentType:
                    MediaType.parse(_getContentType(file.extension ?? '')),
              ),
            );

            final streamedResponse = await request.send();
            final response = await http.Response.fromStream(streamedResponse);

            if (response.statusCode == 200) {
              content = json.decode(utf8.decode(response.bodyBytes))['text'];
              await _createChapterFromContent(title, content);
            } else {
              Fluttertoast.showToast(msg: 'Error processing: ${file.name}');
              continue;
            }
          }
        }
        // Refresh chapter list
        await Provider.of<AppState>(context, listen: false)
            .fetchChapters(widget.projectId);
      }
    } catch (error) {
      print('Error importing documents: $error');
      Fluttertoast.showToast(msg: 'Error importing documents');
    }
  }

  Future<void> _createChapterFromContent(String title, String content) async {
    try {
      final response = await http.post(
        Uri.parse('$apiUrl/chapters?project_id=${widget.projectId}'),
        headers: await getAuthHeaders(),
        body: json.encode({
          'title': title,
          'content': content,
          'project_id': widget.projectId,
        }),
      );

      if (response.statusCode == 200) {
        Fluttertoast.showToast(msg: 'Imported: $title');
      } else {
        Fluttertoast.showToast(msg: 'Error importing: $title');
      }
    } catch (error) {
      print('Error creating chapter: $error');
      Fluttertoast.showToast(msg: 'Error creating chapter: $title');
    }
  }

  String _getContentType(String extension) {
    switch (extension.toLowerCase()) {
      case 'pdf':
        return 'application/pdf';
      case 'doc':
      case 'docx':
        return 'application/msword';
      case 'txt':
        return 'text/plain';
      case 'md':
        return 'text/markdown';
      default:
        return 'application/octet-stream';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        // Left panel - Chapter list
        SizedBox(
          width: 300,
          child: Card(
            margin: const EdgeInsets.all(16),
            child: Column(
              children: [
                _buildCreateChapterButton(),
                if (_isLoading)
                  _buildLoadingIndicator()
                else if (_error != null)
                  _buildErrorState()
                else if (_displayedChapters.isEmpty)
                  Expanded(child: _buildEmptyState())
                else
                  _buildChapterList(),
              ],
            ),
          ),
        ),
        // Right panel - Editor
        Expanded(
          child: Card(
            margin: const EdgeInsets.all(16),
            child: Column(
              children: [
                _buildEditorHeader(),
                _buildEditorContent(),
              ],
            ),
          ),
        ),
      ],
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

  Widget _buildChapterList() {
    if (_isLoading) {
      return _buildLoadingIndicator();
    }

    if (_error != null) {
      return _buildErrorState();
    }

    if (_displayedChapters.isEmpty) {
      return _buildEmptyState();
    }

    return Expanded(
      child: ListView.builder(
        controller: _chapterListController,
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: _displayedChapters.length + (_isLoadingMore ? 1 : 0),
        itemBuilder: (context, index) {
          if (index == _displayedChapters.length) {
            return _buildLoadingIndicator();
          }

          final chapter = _displayedChapters[index];
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
          IconButton(
            icon: const Icon(Icons.upload_file),
            onPressed: _importDocuments,
            tooltip: 'Import documents',
          ),
          const SizedBox(width: 8),
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

  // Add new widgets for different states
  Widget _buildLoadingIndicator() {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16),
      alignment: Alignment.center,
      child: const CircularProgressIndicator(),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.book_outlined,
            size: 48,
            color: Theme.of(context).colorScheme.secondary,
          ),
          const SizedBox(height: 16),
          Text(
            'No chapters yet',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          Text(
            'Create a new chapter to get started',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ],
      ),
    );
  }
}
