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
  String _response = '';
  bool _isLoading = false;

  Future<void> _submitQuery() async {
    if (_queryController.text.isEmpty) return;

    setState(() {
      _isLoading = true;
      _response = '';
    });

    try {
      final headers = await getAuthHeaders();
      headers['Content-Type'] = 'application/json';
      final response = await http.post(
        Uri.parse(
            '$apiUrl/knowledge-base/query?project_id=${widget.projectId}'),
        headers: headers,
        body: utf8.encode(json.encode({
          'query': _queryController.text,
          'chatHistory': [],
        })),
      );

      final jsonResponse = json.decode(utf8.decode(response.bodyBytes));
      setState(() {
        _response = jsonResponse['response'];
        _isLoading = false;
      });
    } catch (error) {
      setState(() {
        _response = 'Error processing query: $error';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
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
            maxLines: 3,
          ),
          const SizedBox(height: 16),
          if (_isLoading)
            const Center(child: CircularProgressIndicator())
          else if (_response.isNotEmpty)
            Expanded(
              child: Card(
                elevation: 3,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: SingleChildScrollView(
                    child: Text(_response),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
