import 'package:flutter/material.dart';
import '../components/create_chapter.dart';

class CreateScreen extends StatelessWidget {
  const CreateScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Create')),
      body: const CreateChapter(),
    );
  }
}
