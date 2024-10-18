import 'package:flutter/material.dart';
import '../components/codex.dart';

class CodexScreen extends StatelessWidget {
  const CodexScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: const Codex(),
      floatingActionButton: Hero(
        tag: 'addCodexItemFab',
        child: FloatingActionButton(
          onPressed: () {
            _showAddCodexItemDialog(context);
          },
          child: const Icon(Icons.add),
          tooltip: 'Add Codex Item',
        ),
      ),
    );
  }

  void _showAddCodexItemDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('Add Codex Item'),
          content:
              const Text('Implement the form to add a new codex item here.'),
          actions: <Widget>[
            TextButton(
              child: const Text('Cancel'),
              onPressed: () {
                Navigator.of(context).pop();
              },
            ),
            TextButton(
              child: const Text('Add'),
              onPressed: () {
                // Implement the logic to add a new codex item
                Navigator.of(context).pop();
              },
            ),
          ],
        );
      },
    );
  }
}
