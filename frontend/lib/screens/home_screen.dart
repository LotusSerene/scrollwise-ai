import 'package:flutter/material.dart';
import '../components/dashboard.dart';
import '../components/codex.dart';
import '../components/validity.dart';
import '../components/knowledge_base.dart';
import '../components/query.dart';
import '../components/create_chapter.dart';
import '../components/project_settings.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import '../components/editor.dart';
import '../components/codex_generation.dart';
import '../utils/auth.dart';
import '../utils/constants.dart';
import './character_relationships_screen.dart';
import './character_journey_screen.dart';
import './timeline_screen.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class HomeScreen extends StatefulWidget {
  const HomeScreen({Key? key}) : super(key: key);

  @override
  _HomeScreenState createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with TickerProviderStateMixin {
  TabController? _tabController;
  Map<String, bool> _permissions = {};
  bool _isOwner = false;
  late Future<void> _permissionsFuture;

  @override
  void initState() {
    super.initState();
    _permissionsFuture = _loadPermissions();
  }

  @override
  void dispose() {
    _tabController?.dispose();
    super.dispose();
  }

  Future<void> _loadPermissions() async {
    final appState = Provider.of<AppState>(context, listen: false);
    final projectId = appState.currentProjectId;

    if (projectId == null) return;

    try {
      final response = await http.get(
        Uri.parse('$apiUrl/collaborations/project/$projectId/permissions'),
        headers: await getAuthHeaders(),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() {
          _permissions = Map<String, bool>.from(data['permissions']);
          _isOwner = data['is_owner'];
        });
      } else {
        setState(() {
          _permissions = {};
          _isOwner = false;
        });
      }
    } catch (e) {
      setState(() {
        _permissions = {};
        _isOwner = false;
      });
    }
  }

  void _initializeTabController(List<TabItem> authorizedTabs) {
    // Dispose of the old controller if it exists
    _tabController?.dispose();

    // Create a new controller with the current number of tabs
    _tabController = TabController(
      length: authorizedTabs.length,
      vsync: this,
      initialIndex: 0,
    );
  }

  bool _hasPermission(String permission) {
    if (_isOwner) return true;
    return _permissions[permission] == true;
  }

  List<TabItem> _getAuthorizedTabs() {
    final List<TabItem> authorizedTabs = [];

    // Dashboard is always visible
    authorizedTabs.add(TabItem(icon: Icons.dashboard, label: 'Dashboard'));

    // Editor requires write_chapters permission
    if (_hasPermission('write_chapters')) {
      authorizedTabs.add(TabItem(icon: Icons.edit, label: 'Editor'));
    }

    // Codex requires manage_codex permission
    if (_hasPermission('manage_codex')) {
      authorizedTabs.add(TabItem(icon: Icons.book, label: 'Codex'));
      authorizedTabs
          .add(TabItem(icon: Icons.auto_awesome, label: 'Codex Generation'));
    }

    // Character features require manage_characters permission
    if (_hasPermission('manage_characters')) {
      authorizedTabs
          .add(TabItem(icon: Icons.people, label: 'Character Relationships'));
      authorizedTabs
          .add(TabItem(icon: Icons.timeline, label: 'Character Journey'));
    }

    // Timeline requires manage_timeline permission
    if (_hasPermission('manage_timeline')) {
      authorizedTabs.add(TabItem(icon: Icons.schedule, label: 'Timeline'));
    }

    // Validity checks require check_validity permission
    if (_hasPermission('check_validity')) {
      authorizedTabs.add(TabItem(icon: Icons.check_circle, label: 'Validity'));
    }

    // Knowledge base features require manage_knowledge_base permission
    if (_hasPermission('manage_knowledge_base')) {
      authorizedTabs
          .add(TabItem(icon: Icons.psychology, label: 'Knowledge Base'));
      authorizedTabs.add(TabItem(icon: Icons.search, label: 'Query'));
    }

    // Chapter generation requires generate_chapters permission
    if (_hasPermission('generate_chapters')) {
      authorizedTabs.add(TabItem(icon: Icons.add_circle, label: 'Generate'));
    }

    // Project settings only available to owner
    if (_isOwner) {
      authorizedTabs
          .add(TabItem(icon: Icons.settings, label: 'Project Settings'));
    }

    return authorizedTabs;
  }

  Widget _buildNoProjectSelected() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.folder_open,
            size: 64,
            color: Theme.of(context).colorScheme.secondary,
          ),
          const SizedBox(height: 16),
          Text(
            'No Project Selected',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: Theme.of(context).colorScheme.secondary,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            'Please select a project to get started.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final appState = Provider.of<AppState>(context);
    final projectId = appState.currentProjectId;

    if (projectId == null) {
      return Scaffold(body: _buildNoProjectSelected());
    }

    return FutureBuilder<void>(
      future: _permissionsFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }

        // Get authorized tabs after permissions are loaded
        final authorizedTabs = _getAuthorizedTabs();

        // Initialize tab controller if needed
        if (_tabController?.length != authorizedTabs.length) {
          _initializeTabController(authorizedTabs);
        }

        // If we don't have a tab controller yet, show loading
        if (_tabController == null) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }

        return Scaffold(
          appBar: AppBar(
            elevation: 0,
            title: Row(
              children: [
                Icon(Icons.book, color: Theme.of(context).colorScheme.primary),
                const SizedBox(width: 8),
                const Text('Story Builder'),
              ],
            ),
            actions: [
              if (_hasPermission('refresh_data'))
                IconButton(
                  icon: const Icon(Icons.refresh),
                  tooltip: 'Refresh',
                  onPressed: () {
                    appState.refreshProjectData();
                  },
                ),
              IconButton(
                icon: const Icon(Icons.exit_to_app),
                tooltip: 'Back to Projects',
                onPressed: () =>
                    Navigator.pushReplacementNamed(context, '/projects'),
              ),
            ],
            bottom: PreferredSize(
              preferredSize: const Size.fromHeight(48),
              child: TabBar(
                controller: _tabController,
                isScrollable: true,
                indicatorWeight: 3,
                indicatorColor: Theme.of(context).colorScheme.primary,
                tabs: authorizedTabs
                    .map((tab) => Tab(
                          icon: Icon(tab.icon, size: 20),
                          text: tab.label,
                        ))
                    .toList(),
              ),
            ),
          ),
          body: TabBarView(
            controller: _tabController,
            physics: const NeverScrollableScrollPhysics(),
            children: authorizedTabs.map((tab) {
              return _buildTabContent(tab.label, projectId);
            }).toList(),
          ),
        );
      },
    );
  }

  Widget _buildTabContent(String tabLabel, String projectId) {
    try {
      switch (tabLabel) {
        case 'Dashboard':
          return Dashboard(
            projectId: projectId,
            onProgressChanged: (chapters, codexEntries, wordCount) {
              Provider.of<AppState>(context, listen: false)
                  .updateProgress(chapters, codexEntries, wordCount);
            },
          );
        case 'Editor':
          if (!_hasPermission('write_chapters')) {
            print('No write_chapters permission');
            return _buildNoPermissionView('write_chapters');
          }
          return Editor(projectId: projectId);
        case 'Codex':
          return _hasPermission('manage_codex')
              ? Codex(projectId: projectId)
              : _buildNoPermissionView('manage_codex');
        case 'Codex Generation':
          return _hasPermission('manage_codex')
              ? CodexGeneration(projectId: projectId)
              : _buildNoPermissionView('manage_codex');
        case 'Character Relationships':
          return _hasPermission('manage_characters')
              ? CharacterRelationshipsScreen(projectId: projectId)
              : _buildNoPermissionView('manage_characters');
        case 'Character Journey':
          return _hasPermission('manage_characters')
              ? CharacterJourneyScreen(projectId: projectId)
              : _buildNoPermissionView('manage_characters');
        case 'Timeline':
          return _hasPermission('manage_timeline')
              ? TimelineScreen(projectId: projectId)
              : _buildNoPermissionView('manage_timeline');
        case 'Validity':
          return _hasPermission('check_validity')
              ? Validity(projectId: projectId)
              : _buildNoPermissionView('check_validity');
        case 'Knowledge Base':
          return _hasPermission('manage_knowledge_base')
              ? KnowledgeBase(projectId: projectId)
              : _buildNoPermissionView('manage_knowledge_base');
        case 'Query':
          if (!_hasPermission('manage_knowledge_base')) {
            print('No manage_knowledge_base permission');
            return _buildNoPermissionView('manage_knowledge_base');
          }
          return Query(projectId: projectId);
        case 'Generate':
          return _hasPermission('generate_chapters')
              ? CreateChapter(projectId: projectId)
              : _buildNoPermissionView('generate_chapters');
        case 'Project Settings':
          return _isOwner
              ? ProjectSettings(projectId: projectId)
              : _buildNoPermissionView('owner');
        default:
          return const Center(child: Text('Unknown tab'));
      }
    } catch (e) {
      print('Error building tab content: $e');
      return Center(child: Text('Error loading content: $e'));
    }
  }

  Widget _buildNoPermissionView(String permission) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.lock_outline,
            size: 64,
            color: Theme.of(context).colorScheme.error,
          ),
          const SizedBox(height: 16),
          Text(
            'No Permission',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: Theme.of(context).colorScheme.error,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            'You need the "$permission" permission to access this feature',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ],
      ),
    );
  }
}

class TabItem {
  final IconData icon;
  final String label;

  TabItem({required this.icon, required this.label});
}
