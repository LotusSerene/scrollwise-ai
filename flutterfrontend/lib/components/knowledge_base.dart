import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';
import 'package:file_picker/file_picker.dart'; // Import FilePicker

class KnowledgeBase extends StatefulWidget {
  const KnowledgeBase({Key? key}) : super(key: key);

  @override
  State<KnowledgeBase> createState() => _KnowledgeBaseState();
}

class _KnowledgeBaseState extends State<KnowledgeBase> {
  List<dynamic> _knowledgeBaseContent = [];
  final TextEditingController _textController = TextEditingController();
  var _selectedFile;

  @override
  void initState() {
    super.initState();
    _fetchKnowledgeBaseContent();
  }

  Future<void> _fetchKnowledgeBaseContent() async {
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/knowledge-base'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 200) {
        setState(() {
          _knowledgeBaseContent = json.decode(response.body)['content'];
        });
      } else {
        Fluttertoast.showToast(msg: 'Error fetching knowledge base content');
      }
    } catch (error) {
      print('Error fetching knowledge base content: $error');
      Fluttertoast.showToast(msg: 'Error fetching knowledge base content');
    }
  }

  Future<void> _handleTextSubmit() async {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    try {
      final headers = <String, String>{
        ...await getAuthHeaders(),
        'Content-Type': 'application/x-www-form-urlencoded',
      };
      final response = await http.post(
        Uri.parse('$apiUrl/knowledge-base/'),
        headers: headers,
        body: {
          'documents': text,
          'metadata': json.encode({'type': 'text'})
        },
      );
      final jsonResponse = json.decode(response.body);
      if (response.statusCode == 201 && !jsonResponse.containsKey('error')) {
        setState(() {
          _textController.clear();
        });
        _fetchKnowledgeBaseContent();
        Fluttertoast.showToast(msg: 'Text added to knowledge base');
      } else {
        final errorMessage = jsonResponse['error'] ?? 'Error adding text to knowledge base';
        Fluttertoast.showToast(msg: errorMessage);
      }
    } catch (error) {
      print('Error adding text to knowledge base: $error');
      Fluttertoast.showToast(msg: 'Error adding text to knowledge base');
    }
  }

  Future<void> _handleFileUpload(BuildContext context) async {
    if (_selectedFile == null) return;

    try {
      final headers = <String, String>{
        ...await getAuthHeaders(),
        'Content-Type': 'multipart/form-data',
      };
      final request =
          http.MultipartRequest('POST', Uri.parse('$apiUrl/knowledge-base'));
      request.headers.addAll(headers);
      final file =
          await http.MultipartFile.fromPath('file', _selectedFile.path);
      request.files.add(file);
      request.fields['metadata'] =
          json.encode({'type': 'file', 'filename': _selectedFile.path});
      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);
      final jsonResponse = json.decode(response.body);

      if (response.statusCode == 201 && !jsonResponse.containsKey('error')) {
        setState(() {
          _selectedFile = null;
        });
        _fetchKnowledgeBaseContent();
        Fluttertoast.showToast(msg: 'File uploaded successfully');
      } else {
        final errorMessage = jsonResponse['error'] ?? 'Error uploading file';
        Fluttertoast.showToast(msg: errorMessage);
      }
    } catch (error) {
      print('Error uploading file: $error');
      Fluttertoast.showToast(msg: 'Error uploading file');
    }
  }

  Future<void> _handleDelete(String embeddingId) async {
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/knowledge-base/$embeddingId'),
        headers: await getAuthHeaders(),
      );
      final jsonResponse = json.decode(response.body);
      if (response.statusCode == 204 && !jsonResponse.containsKey('error')) {
        setState(() {
          _knowledgeBaseContent
              .removeWhere((item) => item['embedding_id'] == embeddingId);
        });
        Fluttertoast.showToast(msg: 'Item deleted from knowledge base');
      } else {
        final errorMessage = jsonResponse['error'] ?? 'Error deleting item from knowledge base';
        Fluttertoast.showToast(msg: errorMessage);
      }
    } catch (error) {
      print('Error deleting item from knowledge base: $error');
      Fluttertoast.showToast(msg: 'Error deleting item from knowledge base');
    }
  }

  @override
  Widget build(BuildContext context) {
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
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Knowledge Base',
            style: TextStyle(
              color: Color(0xFF007bff),
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 20),
          Flexible(
            fit: FlexFit.loose,
            child: ListView.builder(
              itemCount: _knowledgeBaseContent.length,
              itemBuilder: (context, index) {
                final item = _knowledgeBaseContent[index];
                final content = item['content'];
                return Card(
                  color: const Color(0xFF343a40),
                  child: ListTile(
                    title: Text(
                      'Type: ${item['type']}',
                      style: const TextStyle(color: Colors.white),
                    ),
                    subtitle: Text(
                      'Content: ${content.length > 100 ? content.substring(0, 100) + '...' : content}',
                      style: const TextStyle(color: Colors.white70),
                    ),
                    trailing: IconButton(
                      onPressed: () => _handleDelete(item['embedding_id']),
                      icon: const Icon(Icons.delete, color: Colors.red),
                    ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 20),
          TextField(
            controller: _textController,
            decoration: const InputDecoration(
              hintText: 'Add text to knowledge base',
              hintStyle: TextStyle(color: Colors.white),
              enabledBorder: OutlineInputBorder(
                borderSide: BorderSide(color: Color(0xFFced4da)),
              ),
              focusedBorder: OutlineInputBorder(
                borderSide: BorderSide(color: Color(0xFF007bff)),
              ),
            ),
            style: const TextStyle(color: Colors.white),
            maxLines: null,
          ),
          ElevatedButton(
            onPressed: _handleTextSubmit,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF007bff),
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              textStyle: const TextStyle(fontSize: 16),
            ),
            child: const Text('Add Text'),
          ),
          const SizedBox(height: 10),
          ElevatedButton(
            onPressed: () async {
              final result = await FilePicker.platform.pickFiles();
              if (result != null) {
                setState(() {
                  _selectedFile = result.files.single;
                });
                _handleFileUpload(context);
              } else {
                // User canceled the picker
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF007bff),
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              textStyle: const TextStyle(fontSize: 16),
            ),
            child: const Text('Upload Document'),
          ),
        ],
      ),
    );
  }
}
