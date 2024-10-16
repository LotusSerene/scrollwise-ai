import 'package:flutter/material.dart';
import '../components/knowledge_base.dart';

class KnowledgeBaseScreen extends StatelessWidget {
  const KnowledgeBaseScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Knowledge Base')),
      body: const KnowledgeBase(),
    );
  }
}
