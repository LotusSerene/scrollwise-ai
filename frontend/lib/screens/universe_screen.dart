import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

import '../utils/constants.dart';
import 'package:intl/intl.dart';
import 'package:logging/logging.dart';

final _logger = Logger('Universes');

class UniverseScreen extends StatefulWidget {
  final String universeId;

  const UniverseScreen({Key? key, required this.universeId}) : super(key: key);

  @override
  UniverseScreenState createState() => UniverseScreenState();
}

class UniverseScreenState extends State<UniverseScreen> {
  Map<String, dynamic> _universeData = {};
  List<dynamic> _codexItems = [];
  Map<String, List<dynamic>> _knowledgeBaseItems = {};
  bool _isLoading = true;
  List<dynamic> _projects = [];
  String _selectedFilter = 'All';
  final Map<String, bool> _expandedSections = {
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
      );
      if (universeResponse.statusCode == 200) {
        _universeData = json.decode(utf8.decode(universeResponse.bodyBytes));
      } else {
        throw Exception('Failed to load universe data');
      }

      // Fetch projects
      final projectsResponse = await http.get(
        Uri.parse('$apiUrl/universes/${widget.universeId}/projects'),
      );
      if (projectsResponse.statusCode == 200) {
        _projects = json.decode(utf8.decode(projectsResponse.bodyBytes));
      } else {
        throw Exception('Failed to load projects');
      }

      // Fetch codex items
      final codexResponse = await http.get(
        Uri.parse('$apiUrl/universes/${widget.universeId}/codex'),
      );
      if (codexResponse.statusCode == 200) {
        _codexItems = json.decode(utf8.decode(codexResponse.bodyBytes));
      }

      // Fetch knowledge base items
      final knowledgeBaseResponse = await http.get(
        Uri.parse('$apiUrl/universes/${widget.universeId}/knowledge-base'),
      );
      if (knowledgeBaseResponse.statusCode == 200) {
        Map<String, dynamic> responseData =
            json.decode(utf8.decode(knowledgeBaseResponse.bodyBytes));
        _knowledgeBaseItems = Map<String, List<dynamic>>.from(responseData);
      }

      setState(() {
        _isLoading = false;
      });
    } catch (error) {
      _logger.severe('Error fetching universe data: $error');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content:
                Text('Error fetching universe data: ${error.toString()}')));
        setState(() {
          _isLoading = false;
        });
      }
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
        elevation: 0,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : CustomScrollView(
              slivers: [
                SliverToBoxAdapter(
                  child: _buildUniverseHeader(),
                ),
                SliverToBoxAdapter(
                  child: _buildFilterChips(),
                ),
                SliverPadding(
                  padding: const EdgeInsets.all(16),
                  sliver: SliverList(
                    delegate: SliverChildListDelegate([
                      if (_selectedFilter == 'All' ||
                          _selectedFilter == 'Projects')
                        _buildCollapsibleSection('Projects', _projects),
                      if (_selectedFilter == 'All' ||
                          _selectedFilter == 'Codex')
                        _buildCollapsibleSection('Codex', _codexItems),
                      if (_selectedFilter == 'All' ||
                          _selectedFilter == 'Knowledge Base')
                        _buildCollapsibleSection(
                            'Knowledge Base', _knowledgeBaseItems),
                    ]),
                  ),
                ),
              ],
            ),
    );
  }

  Widget _buildUniverseHeader() {
    return Container(
      color: Theme.of(context).colorScheme.surface,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.public,
                  size: 32, color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _universeData['name'] ?? 'Universe',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    Text(
                      'Created ${DateFormat('MMM d, yyyy').format(DateTime.parse(_universeData['created_at'] ?? DateTime.now().toString()))}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (_universeData['description'] != null) ...[
            const SizedBox(height: 16),
            Text(
              _universeData['description'],
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
          const SizedBox(height: 16),
          _buildStatisticCards(),
        ],
      ),
    );
  }

  Widget _buildStatisticCards() {
    return Row(
      children: [
        Expanded(
          child: _buildStatCard(
            'Projects',
            _projects.length.toString(),
            Icons.folder_special,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _buildStatCard(
            'Codex Entries',
            _codexItems.length.toString(),
            Icons.book,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _buildStatCard(
            'Knowledge Base',
            _knowledgeBaseItems.values
                .fold(0, (sum, list) => sum + list.length)
                .toString(),
            Icons.psychology,
          ),
        ),
      ],
    );
  }

  Widget _buildStatCard(String title, String value, IconData icon) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Icon(icon, color: Theme.of(context).colorScheme.primary),
            const SizedBox(height: 8),
            Text(
              value,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            Text(
              title,
              style: Theme.of(context).textTheme.bodySmall,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFilterChips() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          _buildFilterChip('All'),
          const SizedBox(width: 8),
          _buildFilterChip('Projects'),
          const SizedBox(width: 8),
          _buildFilterChip('Codex'),
          const SizedBox(width: 8),
          _buildFilterChip('Knowledge Base'),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String label) {
    return FilterChip(
      selected: _selectedFilter == label,
      label: Text(label),
      onSelected: (bool selected) {
        setState(() {
          _selectedFilter = selected ? label : 'All';
        });
      },
    );
  }

  Widget _buildCollapsibleSection(String title, dynamic items) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ListTile(
            title: Text(
              title,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: Theme.of(context).colorScheme.primary,
                  ),
            ),
            leading: Icon(
              _getSectionIcon(title),
              color: Theme.of(context).colorScheme.primary,
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
              _buildItemsList(title, items),
        ],
      ),
    );
  }

  IconData _getSectionIcon(String section) {
    switch (section) {
      case 'Projects':
        return Icons.folder_special;
      case 'Codex':
        return Icons.book;
      case 'Knowledge Base':
        return Icons.psychology;
      default:
        return Icons.circle;
    }
  }

  Widget _buildItemsList(String title, List<dynamic> items) {
    if (items.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Center(
          child: Text(
            'No ${title.toLowerCase()} found',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color:
                      Theme.of(context).colorScheme.onSurface.withOpacity(0.6),
                ),
          ),
        ),
      );
    }

    return ListView.separated(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: items.length,
      separatorBuilder: (context, index) => const Divider(height: 1),
      itemBuilder: (context, index) {
        final item = items[index];
        return ListTile(
          title: Text(item['name'] ?? item['title'] ?? 'Untitled'),
          subtitle: Text(
            item['description'] ?? '',
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          leading: Icon(_getItemIcon(title)),
          trailing: const Icon(Icons.chevron_right),
          onTap: () {
            if (title == 'Projects') {
              _showProjectDetails(item);
            } else if (title == 'Codex') {
              _showCodexDetails(item);
            }
          },
        );
      },
    );
  }

  IconData _getItemIcon(String section) {
    switch (section) {
      case 'Projects':
        return Icons.folder_open;
      case 'Codex':
        return Icons.article;
      default:
        return Icons.circle;
    }
  }

  Widget _buildKnowledgeBaseSection(
      Map<String, List<dynamic>> knowledgeBaseByProject) {
    if (knowledgeBaseByProject.isEmpty) {
      return const ListTile(title: Text('No knowledge base items'));
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
                const SizedBox(height: 8),
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
    return '${text.substring(0, maxLength)}...';
  }
}
