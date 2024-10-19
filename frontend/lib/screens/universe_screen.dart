import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';

class UniverseScreen extends StatefulWidget {
  final String universeId;

  const UniverseScreen({Key? key, required this.universeId}) : super(key: key);

  @override
  _UniverseScreenState createState() => _UniverseScreenState();
}

class _UniverseScreenState extends State<UniverseScreen> {
  Map<String, dynamic> _universeData = {};
  List<dynamic> _codexItems = [];
  List<dynamic> _knowledgeBaseItems = [];
  bool _isLoading = true;
  List<dynamic> _projects = [];

  @override
  void initState() {
    super.initState();
    _fetchUniverseData();
    _fetchUniverseProjects();
  }

  Future<void> _fetchUniverseData() async {
    setState(() {
      _isLoading = true;
    });
    try {
      final universeResponse = await http.get(
        Uri.parse('$apiUrl/universes/${widget.universeId}'),
        headers: await getAuthHeaders(),
      );
      if (universeResponse.statusCode == 200) {
        _universeData = json.decode(universeResponse.body);
      }

      final codexResponse = await http.get(
        Uri.parse('$apiUrl/universes/${widget.universeId}/codex'),
        headers: await getAuthHeaders(),
      );
      if (codexResponse.statusCode == 200) {
        _codexItems = json.decode(codexResponse.body);
      }

      final knowledgeBaseResponse = await http.get(
        Uri.parse('$apiUrl/universes/${widget.universeId}/knowledge-base'),
        headers: await getAuthHeaders(),
      );
      if (knowledgeBaseResponse.statusCode == 200) {
        _knowledgeBaseItems = json.decode(knowledgeBaseResponse.body);
      }

      setState(() {
        _isLoading = false;
      });
    } catch (error) {
      print('Error fetching universe data: $error');
      Fluttertoast.showToast(msg: 'Error fetching universe data');
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _fetchUniverseProjects() async {
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/universes/${widget.universeId}/projects'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 200) {
        setState(() {
          _projects = json.decode(response.body);
        });
      } else {
        final errorData = json.decode(response.body);
        throw Exception(errorData['detail'] ?? 'Unknown error occurred');
      }
    } catch (error) {
      print('Error fetching universe projects: $error');
      Fluttertoast.showToast(msg: 'Error fetching universe projects: ${error.toString()}');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_universeData['name'] ?? 'Universe'),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildSection('Projects', _projects),
                  _buildSection('Codex', _codexItems),
                  _buildSection('Knowledge Base', _knowledgeBaseItems),
                ],
              ),
            ),
    );
  }

  Widget _buildSection(String title, List<dynamic> items) {
    return Card(
      margin: const EdgeInsets.all(8.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Text(
              title,
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
          ListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: items.length,
            itemBuilder: (context, index) {
              final item = items[index];
              return ListTile(
                title: Text(item['name'] ?? item['title'] ?? 'Untitled'),
                subtitle: Text(item['description'] ?? ''),
                onTap: () {
                  // Implement item details view
                },
              );
            },
          ),
        ],
      ),
    );
  }
}
