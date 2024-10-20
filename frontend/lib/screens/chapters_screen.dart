import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';

class ChaptersScreen extends StatefulWidget {
  final String projectId;

  const ChaptersScreen({Key? key, required this.projectId}) : super(key: key);

  @override
  State<ChaptersScreen> createState() => _ChaptersScreenState();
}

class _ChaptersScreenState extends State<ChaptersScreen> {
  bool _isLoading = true;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _fetchChapters();
  }

  Future<void> _fetchChapters() async {
    setState(() {
      _isLoading = true;
      _error = '';
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
        Provider.of<AppState>(context, listen: false).setChapters(chapters);
        setState(() {
          _isLoading = false;
        });
      } else {
        setState(() {
          _error = 'Error fetching chapters: ${response.statusCode}';
          _isLoading = false;
        });
      }
    } catch (error) {
      setState(() {
        _error = 'Error fetching chapters: $error';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final appState = Provider.of<AppState>(context);
    final chapters = appState.chapters;

    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error.isNotEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(_error, style: const TextStyle(color: Colors.red)),
            ElevatedButton(
              onPressed: _fetchChapters,
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    return Scaffold( // Wrapped ListView.builder in Scaffold
      appBar: AppBar(title: const Text('Chapters')),
      body: RefreshIndicator(
        onRefresh: _fetchChapters,
        child: ListView.builder(
          itemCount: chapters.length,
          itemBuilder: (context, index) {
            final chapter = chapters[index];
            return ListTile(
              title: Text(chapter['title']),
              onTap: () {
                Navigator.pushNamed(context, '/editor', arguments: chapter['id']);
              },
            );
          },
        ),
      ),
    );
  }
}