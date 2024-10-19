import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';
import 'package:intl/intl.dart';

class UniverseScreen extends StatefulWidget {
  final String universeId;

  const UniverseScreen({Key? key, required this.universeId}) : super(key: key);

  @override
  _UniverseScreenState createState() => _UniverseScreenState();
}

class _UniverseScreenState extends State<UniverseScreen> {
  Map<String, dynamic> _universeData = {};
  List<dynamic> _codexItems = [];
  Map<String, List<dynamic>> _knowledgeBaseItems = {};
  bool _isLoading = true;
  List<dynamic> _projects = [];
  String _selectedFilter = 'All';
  Map<String, bool> _expandedSections = {
    'Projects': true,
    'Codex': true,
    'Knowledge Base': true,
  };

  @override
  void initState() {
    super.initState();
    _fetchUniverseData();
  }

  Future<void> _fetchUniverseData() async {
    setState(() {
      _isLoading = true;
    });
    try {
      // Fetch universe data
      final universeResponse = await http.get(
        Uri.parse('$apiUrl/universes/${widget.universeId}'),
        headers: await getAuthHeaders(),
      );
      if (universeResponse.statusCode == 200) {
        _universeData = json.decode(utf8.decode(universeResponse.bodyBytes));
      }

      // Fetch projects
      final projectsResponse = await http.get(
        Uri.parse('$apiUrl/universes/${widget.universeId}/projects'),
        headers: await getAuthHeaders(),
      );
      if (projectsResponse.statusCode == 200) {
        _projects = json.decode(utf8.decode(projectsResponse.bodyBytes));
      }

      // Fetch codex items
      final codexResponse = await http.get(
        Uri.parse('$apiUrl/universes/${widget.universeId}/codex'),
        headers: await getAuthHeaders(),
      );
      if (codexResponse.statusCode == 200) {
        _codexItems = json.decode(utf8.decode(codexResponse.bodyBytes));
      }

      // Fetch knowledge base items
      final knowledgeBaseResponse = await http.get(
        Uri.parse('$apiUrl/universes/${widget.universeId}/knowledge-base'),
        headers: await getAuthHeaders(),
      );
      if (knowledgeBaseResponse.statusCode == 200) {
        Map<String, dynamic> responseData =
            json.decode(utf8.decode(knowledgeBaseResponse.bodyBytes));
        _knowledgeBaseItems =
            Map<String, List<dynamic>>.from(responseData['content']);
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

  void _showProjectDetails(Map<String, dynamic> project) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        int entriesCount = _codexItems
                .where((item) => item['project_id'] == project['id'])
                .length +
            (_knowledgeBaseItems[project['id']]?.length ?? 0);
        return AlertDialog(
          title: Text(project['name']),
          content: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Description: ${project['description']}'),
              Text(
                  'Created: ${DateFormat('yyyy-MM-dd').format(DateTime.parse(project['created_at']))}'),
              Text(
                  'Updated: ${DateFormat('yyyy-MM-dd').format(DateTime.parse(project['updated_at']))}'),
              Text('Entries: $entriesCount'),
            ],
          ),
          actions: [
            TextButton(
              child: const Text('Close'),
              onPressed: () {
                Navigator.of(context).pop();
              },
            ),
          ],
        );
      },
    );
  }

  void _showCodexDetails(Map<String, dynamic> codexItem) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text(codexItem['name']),
          content: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Type: ${codexItem['type']}'),
              Text('Subtype: ${codexItem['subtype'] ?? 'N/A'}'),
              Text('Description: ${codexItem['description']}'),
            ],
          ),
          actions: [
            TextButton(
              child: const Text('Close'),
              onPressed: () {
                Navigator.of(context).pop();
              },
            ),
          ],
        );
      },
    );
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
                  Padding(
                    padding: const EdgeInsets.all(8.0),
                    child: DropdownButton<String>(
                      value: _selectedFilter,
                      onChanged: (String? newValue) {
                        setState(() {
                          _selectedFilter = newValue!;
                        });
                      },
                      items: <String>[
                        'All',
                        'Projects',
                        'Codex',
                        'Knowledge Base'
                      ].map<DropdownMenuItem<String>>((String value) {
                        return DropdownMenuItem<String>(
                          value: value,
                          child: Text(value),
                        );
                      }).toList(),
                    ),
                  ),
                  if (_selectedFilter == 'All' || _selectedFilter == 'Projects')
                    _buildCollapsibleSection('Projects', _projects),
                  if (_selectedFilter == 'All' || _selectedFilter == 'Codex')
                    _buildCollapsibleSection('Codex', _codexItems),
                  if (_selectedFilter == 'All' ||
                      _selectedFilter == 'Knowledge Base')
                    _buildCollapsibleSection(
                        'Knowledge Base', _knowledgeBaseItems),
                ],
              ),
            ),
    );
  }

  Widget _buildCollapsibleSection(String title, dynamic items) {
    return Card(
      margin: const EdgeInsets.all(8.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ListTile(
            title: Text(
              title,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            trailing: IconButton(
              icon: Icon(_expandedSections[title]!
                  ? Icons.expand_less
                  : Icons.expand_more),
              onPressed: () {
                setState(() {
                  _expandedSections[title] = !_expandedSections[title]!;
                });
              },
            ),
          ),
          if (_expandedSections[title]!)
            if (title == 'Knowledge Base')
              _buildKnowledgeBaseSection(items)
            else
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
                      if (title == 'Projects') {
                        _showProjectDetails(item);
                      } else if (title == 'Codex') {
                        _showCodexDetails(item);
                      }
                    },
                  );
                },
              ),
        ],
      ),
    );
  }

  Widget _buildKnowledgeBaseSection(
      Map<String, List<dynamic>> knowledgeBaseByProject) {
    if (knowledgeBaseByProject.isEmpty) {
      return ListTile(title: Text('No knowledge base items'));
    }
    return ListView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: knowledgeBaseByProject.length,
      itemBuilder: (context, index) {
        String projectId = knowledgeBaseByProject.keys.elementAt(index);
        List<dynamic> projectItems = knowledgeBaseByProject[projectId] ?? [];
        String projectName = _projects.firstWhere((p) => p['id'] == projectId,
            orElse: () => {'name': 'Unknown Project'})['name'];

        return ExpansionTile(
          title: Text(projectName),
          children: projectItems
              .map((item) => ListTile(
                    title: Text(item['title'] ?? item['name'] ?? 'Untitled'),
                    subtitle: Text(_truncateText(
                        item['content'] ?? item['description'] ?? '', 100)),
                    onTap: () => _showKnowledgeBaseDetails(item),
                  ))
              .toList(),
        );
      },
    );
  }

  void _showKnowledgeBaseDetails(Map<String, dynamic> item) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text(item['title'] ?? item['name'] ?? 'Untitled'),
          content: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('Type: ${item['type'] ?? 'Unknown'}'),
                SizedBox(height: 8),
                Text(item['content'] ?? item['description'] ?? ''),
              ],
            ),
          ),
          actions: [
            TextButton(
              child: const Text('Close'),
              onPressed: () {
                Navigator.of(context).pop();
              },
            ),
          ],
        );
      },
    );
  }

  String _truncateText(String text, int maxLength) {
    if (text.length <= maxLength) {
      return text;
    }
    return text.substring(0, maxLength) + '...';
  }
}
