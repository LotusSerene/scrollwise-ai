import 'package:flutter/material.dart';
import '../components/dashboard.dart';
import '../utils/auth.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Dashboard')),
      body: RefreshIndicator(
        onRefresh: () async {
          // Implement refresh logic here
        },
        child: const Dashboard(),
      ),
      floatingActionButton: Hero(
        tag: 'createChapterFab',
        child: FloatingActionButton(
          onPressed: () {
            Navigator.pushNamed(context, '/create');
          },
          child: const Icon(Icons.add),
          tooltip: 'Create New Chapter',
        ),
      ),
    );
  }
}
