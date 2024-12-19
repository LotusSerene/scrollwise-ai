import 'package:flutter/material.dart';
import '../components/codex.dart';

class CodexScreen extends StatelessWidget {
  final String projectId;

  const CodexScreen({Key? key, required this.projectId}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Codex'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: Codex(projectId: projectId),
    );
  }
}
