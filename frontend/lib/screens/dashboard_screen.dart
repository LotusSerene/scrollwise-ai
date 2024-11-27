import 'package:flutter/material.dart';
import '../components/dashboard.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';

class DashboardScreen extends StatelessWidget {
  final String projectId;
  const DashboardScreen({Key? key, required this.projectId}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Dashboard')),
      body: RefreshIndicator(
        onRefresh: () async {
          await Provider.of<AppState>(context, listen: false)
              .refreshProjectData();
        },
        child: Dashboard(
          projectId: projectId,
          onProgressChanged: (chapters, codexEntries, wordCount) {
            Provider.of<AppState>(context, listen: false)
                .updateProgress(chapters, codexEntries, wordCount);
          },
        ),
      ),
      floatingActionButton: Hero(
        tag: 'createChapterFab',
        child: FloatingActionButton(
          onPressed: () {
            Navigator.pushNamed(context, '/create',
                arguments: {'projectId': projectId});
          },
          tooltip: 'Create New Chapter',
          child: const Icon(Icons.add),
        ),
      ),
    );
  }
}
