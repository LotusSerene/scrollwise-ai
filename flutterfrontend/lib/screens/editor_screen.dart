import 'package:flutter/material.dart';
import '../components/editor.dart';

class EditorScreen extends StatelessWidget {
  const EditorScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Editor')),
      body: const Editor(),
    );
  }
}
