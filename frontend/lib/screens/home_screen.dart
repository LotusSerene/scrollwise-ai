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

class HomeScreen extends StatefulWidget {
  const HomeScreen({Key? key}) : super(key: key);

  @override
  _HomeScreenState createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with TickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 10, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final appState = Provider.of<AppState>(context);
    final projectId = appState.currentProjectId;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Home'),
        actions: [
          IconButton(
            icon: const Icon(Icons.exit_to_app),
            onPressed: () {
              Navigator.pushReplacementNamed(context, '/projects');
            },
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: const <Widget>[
            Tab(text: 'Dashboard'),
            Tab(text: 'Editor'),
            Tab(text: 'Codex'),
            Tab(text: 'Validity'),
            Tab(text: 'Knowledge Base'),
            Tab(text: 'Query'),
            Tab(text: 'Generate'),
            Tab(text: 'Codex Generation'),
            Tab(text: 'Project Settings'),
            Tab(text: 'Character Relationships'),
          ],
        ),
      ),
      body: projectId == null
          ? const Center(
              child: Text('Select a project'),
            )
          : TabBarView(
              controller: _tabController,
              children: <Widget>[
                Dashboard(
                  projectId: projectId,
                  onProgressChanged: (chapters, codexEntries, wordCount) {
                    // Update the app state with the new progress values.
                    appState.updateProgress(chapters, codexEntries, wordCount);
                  },
                ),
                Editor(projectId: projectId),
                Codex(projectId: projectId),
                Validity(projectId: projectId),
                KnowledgeBase(projectId: projectId),
                Query(projectId: projectId),
                CreateChapter(projectId: projectId),
                CodexGeneration(projectId: projectId),
                ProjectSettings(projectId: projectId),
                CharacterRelationshipsScreen(projectId: projectId),
              ],
            ),
    );
  }
}
