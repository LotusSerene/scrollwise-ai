import 'package:flutter/material.dart';
import '../components/dashboard.dart';
import '../components/codex.dart';
import '../components/validity.dart';
import '../components/knowledge_base.dart';
import '../components/query.dart';
import '../components/create_chapter.dart'; // Import CreateChapter

class HomeScreen extends StatefulWidget {
  const HomeScreen({Key? key}) : super(key: key);

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 6, vsync: this); // Increased length to 6
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Home'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const <Widget>[
            Tab(text: 'Dashboard'),
            Tab(text: 'Codex'),
            Tab(text: 'Validity'),
            Tab(text: 'Knowledge Base'),
            Tab(text: 'Query'),
            Tab(text: 'Generate'), // Added Generate tab
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: const <Widget>[
          Dashboard(),
          Codex(),
          Validity(),
          KnowledgeBase(),
          Query(),
          CreateChapter(), // Added CreateChapter to TabBarView
        ],
      ),
    );
  }
}
