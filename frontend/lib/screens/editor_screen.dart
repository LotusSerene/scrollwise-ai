import 'package:flutter/material.dart';
import '../components/editor.dart';

class EditorScreen extends StatelessWidget {
  const EditorScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final String? chapterId =
        ModalRoute.of(context)?.settings.arguments as String?;

    return Scaffold(
      appBar: AppBar(title: const Text('Editor')),
      body: Editor(projectId: '{{PROJECT_ID}}', chapterId: chapterId),
    );
  }
}
