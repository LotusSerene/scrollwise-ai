import 'package:flutter/material.dart';
import '../components/create_chapter.dart';

class CreateScreen extends StatelessWidget {
  final String projectId;
  const CreateScreen({Key? key, required this.projectId}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Create')),
      body: CreateChapter(projectId: projectId),
    );
  }
}
