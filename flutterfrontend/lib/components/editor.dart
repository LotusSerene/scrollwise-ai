import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';
import 'package:uuid/uuid.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';

class Editor extends StatefulWidget {
  final String? chapterId;

  const Editor({Key? key, this.chapterId}) : super(key: key);

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
    if (widget.chapterId != null) {
      _loadChapter(widget.chapterId!);
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
          Uri.parse('$apiUrl/chapters/$chapterId'),
          headers: headers,
        );
        if (response.statusCode == 200) {
          final chapter = json.decode(response.body);
          setState(() {
            _selectedChapter = chapter;
            _chapterTitleController.text =
                _decodeSpecialCharacters(chapter['title']);
            _chapterContentController.text =
                _decodeSpecialCharacters(chapter['content']);
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

  String _decodeSpecialCharacters(String text) {
    try {
      return utf8.decode(text.codeUnits);
    } catch (e) {
      print('Error decoding text: $e');
      return text;
    }
  }

  String _encodeSpecialCharacters(String text) {
    try {
      return utf8.encode(text).toString();
    } catch (e) {
      print('Error encoding text: $e');
      return text;
    }
  }

  void _handleChapterClick(dynamic chapter) {
    setState(() {
      _selectedChapter = chapter;
      _chapterTitleController.text = chapter['title'];
      _chapterContentController.text = chapter['content'];
      _error = null;
    });
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
        Uri.parse('$apiUrl/chapters/$chapterId'),
        headers: headers,
      );
      final jsonResponse = json.decode(response.body);
      if (response.statusCode == 204 && !jsonResponse.containsKey('error')) {
        Provider.of<AppState>(context, listen: false).removeChapter(chapterId);
        setState(() {
          _selectedChapter = null;
        });
        Fluttertoast.showToast(msg: 'Chapter deleted successfully');
      } else {
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
        'title': _encodeSpecialCharacters(_chapterTitleController.text),
        'content': _encodeSpecialCharacters(_chapterContentController.text),
      };

      http.Response response;
      if (_selectedChapter != null) {
        // Update existing chapter
        response = await http.put(
          Uri.parse('$apiUrl/chapters/$chapterId'),
          headers: headers,
          body: json.encode(requestBody),
        );
      } else {
        // Create new chapter
        response = await http.post(
          Uri.parse('$apiUrl/chapters'),
          headers: headers,
          body: json.encode(requestBody),
        );
      }
      final jsonResponse = json.decode(response.body);
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
          child: Row(
            children: [
              // Chapter list section
              Expanded(
                flex: 1,
                child: Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: const Color(0xFF343a40),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Column(
                    children: [
                      const Text(
                        'Chapters',
                        style: TextStyle(
                          color: Color(0xFF007bff),
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Expanded(
                        child: ListView.builder(
                          itemCount: appState.chapters.length,
                          itemBuilder: (context, index) {
                            final chapter = appState.chapters[index];
                            return ListTile(
                              title: Text(
                                _decodeSpecialCharacters(chapter['title']),
                                style: const TextStyle(color: Colors.white),
                              ),
                              tileColor: _selectedChapter == chapter
                                  ? Colors.grey[700]
                                  : null,
                              onTap: () => _handleChapterClick(chapter),
                              trailing: IconButton(
                                onPressed: () =>
                                    _handleDeleteChapter(chapter['id']),
                                icon:
                                    const Icon(Icons.delete, color: Colors.red),
                              ),
                            );
                          },
                        ),
                      ),
                      const SizedBox(height: 10),
                      ElevatedButton(
                        onPressed: _handleCreateChapter,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF007bff),
                          padding: const EdgeInsets.symmetric(
                              horizontal: 20, vertical: 10),
                          textStyle: const TextStyle(fontSize: 16),
                        ),
                        child: const Text('Create New Chapter'),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 20),
              // Chapter content editor section
              Expanded(
                flex: 2,
                child: Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: const Color(0xFF343a40),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Column(
                    children: [
                      Text(
                        _selectedChapter != null
                            ? 'Edit Chapter: ${_selectedChapter['title']}'
                            : 'Create New Chapter',
                        style: const TextStyle(
                          color: Color(0xFF007bff),
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 10),
                      if (_error != null)
                        Text(
                          _error!,
                          style: const TextStyle(color: Colors.red),
                        ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: _chapterTitleController,
                        decoration: const InputDecoration(
                          labelText: 'Title',
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
                      const SizedBox(height: 15),
                      Expanded(
                        child: TextField(
                          controller: _chapterContentController,
                          maxLines: null,
                          expands: true,
                          decoration: const InputDecoration(
                            labelText: 'Content',
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
                      ),
                      const SizedBox(height: 15),
                      ElevatedButton(
                        onPressed: _handleSaveChapter,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF007bff),
                          padding: const EdgeInsets.symmetric(
                              horizontal: 20, vertical: 10),
                          textStyle: const TextStyle(fontSize: 16),
                        ),
                        child:
                            Text(_selectedChapter != null ? 'Save' : 'Create'),
                      ),
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
}
