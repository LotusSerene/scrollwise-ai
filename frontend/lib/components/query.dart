import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:typed_data';
import '../utils/auth.dart';
import '../utils/constants.dart';

class Query extends StatefulWidget {
  final String projectId;

  const Query({Key? key, required this.projectId}) : super(key: key);

  @override
  State<Query> createState() => _QueryState();
}

class _QueryState extends State<Query> {
  final TextEditingController _queryController = TextEditingController();
  List<Map<String, dynamic>> _chatHistory = [];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadChatHistory();
  }

  Future<void> _loadChatHistory() async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/knowledge-base/chat-history?project_id=${widget.projectId}'),
        headers: headers,
      );
      if (response.statusCode == 200) {
        final jsonResponse = json.decode(utf8.decode(response.bodyBytes));
        setState(() {
          _chatHistory = List<Map<String, dynamic>>.from(jsonResponse['chatHistory']);
        });
      }
    } catch (error) {
      // Handle error
    }
  }

  Future<void> _submitQuery() async {
    if (_queryController.text.isEmpty) return;

    setState(() {
      _isLoading = true;
      _chatHistory.add({'type': 'human', 'content': _queryController.text});
    });

    try {
      final headers = await getAuthHeaders();
      headers['Content-Type'] = 'application/json';
      final response = await http.post(
        Uri.parse('$apiUrl/knowledge-base/query?project_id=${widget.projectId}'),
        headers: headers,
        body: utf8.encode(json.encode({
          'query': _queryController.text,
          'chatHistory': _chatHistory,
        })),
      );

      if (response.statusCode == 200) {
        final jsonResponse = json.decode(utf8.decode(response.bodyBytes));
        setState(() {
          _chatHistory.add({'type': 'ai', 'content': jsonResponse['response']});
          _queryController.clear();
          _isLoading = false;
        });

        // Save chat history
        await _saveChatHistory();
      } else {
        setState(() {
          _chatHistory.removeLast(); // Remove the user's message if the request failed
          _isLoading = false;
        });
        // Handle error
      }
    } catch (error) {
      setState(() {
        _chatHistory.removeLast(); // Remove the user's message if the request failed
        _isLoading = false;
      });
      // Handle error
    }
  }

  Future<void> _saveChatHistory() async {
    try {
      final headers = await getAuthHeaders();
      headers['Content-Type'] = 'application/json';
      await http.put(
        Uri.parse('$apiUrl/chat-history?project_id=${widget.projectId}'),
        headers: headers,
        body: utf8.encode(json.encode({'chatHistory': _chatHistory})),
      );
    } catch (error) {
      // Handle error
    }
  }

  Future<void> _resetChatHistory() async {
    try {
      final headers = await getAuthHeaders();
      await http.delete(
        Uri.parse('$apiUrl/chat-history?project_id=${widget.projectId}'),
        headers: headers,
      );
      setState(() {
        _chatHistory = [];
      });
    } catch (error) {
      // Handle error
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: ListView.builder(
              reverse: true,
              itemCount: _chatHistory.length,
              itemBuilder: (context, index) {
                final message = _chatHistory[index];
                final isUser = message['type'] == 'human';
                return Align(
                  alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: Card(
                    color: isUser ? Colors.blue[100] : Colors.grey[200],
                    child: Padding(
                      padding: const EdgeInsets.all(8.0),
                      child: Text(message['content']),
                    ),
                  ),
                );
              },
            ),
          ),
          TextField(
            controller: _queryController,
            decoration: InputDecoration(
              hintText: 'Enter your query...',
              suffixIcon: IconButton(
                icon: const Icon(Icons.send),
                onPressed: _submitQuery,
              ),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
            onSubmitted: (text) => _submitQuery(),
          ),
          ElevatedButton(
            onPressed: _resetChatHistory,
            child: const Text('Reset Chat History'),
          ),
          if (_isLoading) const LinearProgressIndicator(),
        ],
      ),
    );
  }
}
