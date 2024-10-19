import 'package:flutter/material.dart';
import '../components/query.dart';

class QueryScreen extends StatelessWidget {
  final String projectId;
  const QueryScreen({Key? key, required this.projectId}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Query(projectId: projectId),
    );
  }
}
