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
  _HomeScreenState createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with TickerProviderStateMixin {
  late TabController _tabController;
  final List<TabItem> _tabs = [
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

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 12, vsync: this);
    _tabController.addListener(_handleTabSelection);
  }

  void _handleTabSelection() {
    if (_tabController.indexIsChanging) {
      // Only refresh when switching to the Dashboard tab (index 0)
      if (_tabController.index == 0) {
        final appState = Provider.of<AppState>(context, listen: false);
        if (appState.currentProjectId != null) {
          appState.refreshProjectData();
        }
      }
    }
  }

  @override
  void dispose() {
    _tabController.removeListener(_handleTabSelection);
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final appState = Provider.of<AppState>(context);
    final projectId = appState.currentProjectId;

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
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
            onPressed: () {
              if (projectId != null) {
                appState.refreshProjectData();
              }
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
            tabs: _tabs
                .map((tab) => Tab(
                      icon: Icon(tab.icon, size: 20),
                      text: tab.label,
                    ))
                .toList(),
          ),
        ),
      ),
      body: projectId == null
          ? _buildNoProjectSelected()
          : TabBarView(
              controller: _tabController,
              children: <Widget>[
                Dashboard(
                  projectId: projectId,
                  onProgressChanged: (chapters, codexEntries, wordCount) {
                    appState.updateProgress(chapters, codexEntries, wordCount);
                  },
                ),
                Editor(projectId: projectId),
                Codex(projectId: projectId),
                CodexGeneration(projectId: projectId),
                CharacterRelationshipsScreen(projectId: projectId),
                CharacterJourneyScreen(projectId: projectId),
                TimelineScreen(projectId: projectId),
                Validity(projectId: projectId),
                KnowledgeBase(projectId: projectId),
                Query(projectId: projectId),
                CreateChapter(projectId: projectId),
                ProjectSettings(projectId: projectId),
              ],
            ),
    );
  }

  Widget _buildNoProjectSelected() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.folder_open,
            size: 64,
            color: Theme.of(context).colorScheme.secondary.withOpacity(0.5),
          ),
          const SizedBox(height: 16),
          Text(
            'No Project Selected',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: Theme.of(context).colorScheme.secondary,
                ),
          ),
          const SizedBox(height: 8),
          ElevatedButton.icon(
            icon: const Icon(Icons.folder),
            label: const Text('Select a Project'),
            onPressed: () =>
                Navigator.pushReplacementNamed(context, '/projects'),
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
