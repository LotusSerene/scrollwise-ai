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

import './character_relationships_screen.dart';
import './character_journey_screen.dart';
import './timeline_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({Key? key}) : super(key: key);

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with TickerProviderStateMixin {
  TabController? _tabController;
  late Future<void> _initFuture;

  @override
  void initState() {
    super.initState();
    _initFuture = Future.delayed(Duration.zero);
  }

  @override
  void dispose() {
    _tabController?.dispose();
    super.dispose();
  }

  void _initializeTabController(List<TabItem> tabs) {
    _tabController?.dispose();
    _tabController = TabController(
      length: tabs.length,
      vsync: this,
      initialIndex: 0,
    );
  }

  List<TabItem> _getTabs() {
    return [
      TabItem(icon: Icons.dashboard, label: 'Dashboard'),
      TabItem(icon: Icons.edit, label: 'Editor'),
      TabItem(icon: Icons.book, label: 'Codex'),
      TabItem(icon: Icons.auto_awesome, label: 'Codex Generation'),
      TabItem(icon: Icons.people, label: 'Character Relationships'),
      TabItem(icon: Icons.timeline, label: 'Character Journey'),
      TabItem(icon: Icons.schedule, label: 'Timeline'),
      TabItem(icon: Icons.check_circle, label: 'Validity'),
      TabItem(icon: Icons.psychology, label: 'Knowledge Base'),
      TabItem(icon: Icons.search, label: 'Query'),
      TabItem(icon: Icons.add_circle, label: 'Generate'),
      TabItem(icon: Icons.settings, label: 'Project Settings'),
    ];
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
      future: _initFuture,
      builder: (context, snapshot) {
        final tabs = _getTabs();

        if (_tabController?.length != tabs.length) {
          _initializeTabController(tabs);
        }

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
                tabs: tabs
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
            children: tabs
                .map((tab) => _buildTabContent(tab.label, projectId))
                .toList(),
          ),
        );
      },
    );
  }

  Widget _buildTabContent(String tabLabel, String projectId) {
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
        return Editor(projectId: projectId, readOnly: false);
      case 'Codex':
        return Codex(projectId: projectId);
      case 'Codex Generation':
        return CodexGeneration(projectId: projectId);
      case 'Character Relationships':
        return CharacterRelationshipsScreen(projectId: projectId);
      case 'Character Journey':
        return CharacterJourneyScreen(projectId: projectId);
      case 'Timeline':
        return TimelineScreen(projectId: projectId);
      case 'Validity':
        return Validity(projectId: projectId);
      case 'Knowledge Base':
        return KnowledgeBase(projectId: projectId);
      case 'Query':
        return Query(projectId: projectId);
      case 'Generate':
        return CreateChapter(projectId: projectId);
      case 'Project Settings':
        return ProjectSettings(projectId: projectId);
      default:
        return const Center(child: Text('Unknown tab'));
    }
  }
}

class TabItem {
  final IconData icon;
  final String label;

  TabItem({required this.icon, required this.label});
}
