import 'package:flutter/material.dart';
import '../components/knowledge_base.dart';

class KnowledgeBaseScreen extends StatelessWidget {
  final String projectId;
  const KnowledgeBaseScreen({Key? key, required this.projectId}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Knowledge Base')),
      body: KnowledgeBase(projectId: projectId),
    );
  }
}
