import 'package:flutter/material.dart';
import '../components/dashboard.dart';

class DashboardScreen extends StatelessWidget {
  final String projectId;
  const DashboardScreen({Key? key, required this.projectId}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Dashboard')),
      body: RefreshIndicator(
        onRefresh: () async {
          // Implement refresh logic here
        },
        child: Dashboard(projectId: projectId),
      ),
      floatingActionButton: Hero(
        tag: 'createChapterFab',
        child: FloatingActionButton(
          onPressed: () {
            Navigator.pushNamed(context, '/create', arguments: {'projectId': projectId});
          },
          tooltip: 'Create New Chapter',
          child: const Icon(Icons.add),
        ),
      ),
    );
  }
}
