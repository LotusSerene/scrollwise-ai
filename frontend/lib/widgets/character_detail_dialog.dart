import 'package:flutter/material.dart';
import '../models/character.dart';

class CharacterDetailDialog extends StatelessWidget {
  final Character character;

  const CharacterDetailDialog({Key? key, required this.character})
      : super(key: key);

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(character.name),
      content: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Description:',
                style: Theme.of(context).textTheme.titleMedium),
            Text(character.description),
            const SizedBox(height: 16),
            Text('Backstory:', style: Theme.of(context).textTheme.titleMedium),
            Text(character.backstory.isNotEmpty
                ? character.backstory
                : 'No backstory available'),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
      ],
    );
  }
}
