import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';
import 'package:uuid/uuid.dart';

class Editor extends StatefulWidget {
  const Editor({Key? key}) : super(key: key);

  @override
  State<Editor> createState() => _EditorState();
}

class _EditorState extends State<Editor> {
  List<dynamic> _chapters = [];
  dynamic _selectedChapter;
  final TextEditingController _chapterTitleController = TextEditingController();
  final TextEditingController _chapterContentController =
      TextEditingController();
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchChapters();
  }

  Future<void> _fetchChapters() async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/chapters'),
        headers: headers,
      );
      if (response.statusCode == 200) {
        setState(() {
          _chapters = json.decode(response.body)['chapters'];
        });
      } else {
        Fluttertoast.showToast(msg: 'Error fetching chapters');
      }
    } catch (error) {
      print('Error fetching chapters: $error');
      Fluttertoast.showToast(msg: 'Error fetching chapters');
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
        setState(() {
          _chapters.removeWhere((chapter) => chapter['id'] == chapterId);
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
        'title': _chapterTitleController.text,
        'content': _chapterContentController.text,
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
      if ((response.statusCode == 200 || response.statusCode == 201) && !jsonResponse.containsKey('error')) {
          _fetchChapters();
          setState(() {
            _error = null;
          });
          if(response.statusCode == 200){
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
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF212529), // Dark background color
        borderRadius: BorderRadius.circular(8),
        boxShadow: const [
          BoxShadow(
            color: Color(0x1A000000), // Shadow color with opacity
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
                      itemCount: _chapters.length,
                      itemBuilder: (context, index) {
                        final chapter = _chapters[index];
                        return ListTile(
                          title: Text(
                            chapter['title'],
                            style: const TextStyle(color: Colors.white),
                          ),
                          tileColor: _selectedChapter == chapter
                              ? Colors.grey[700]
                              : null,
                          onTap: () => _handleChapterClick(chapter),
                          trailing: IconButton(
                            onPressed: () =>
                                _handleDeleteChapter(chapter['id']),
                            icon: const Icon(Icons.delete, color: Colors.red),
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
                    child: Text(_selectedChapter != null ? 'Save' : 'Create'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
