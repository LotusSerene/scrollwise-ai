import 'package:flutter/material.dart';

class CreateRelationshipDialog extends StatefulWidget {
  final List<Map<String, String>> characters;
  final Function(String, String, String) onCreateRelationship;

  const CreateRelationshipDialog({
    Key? key,
    required this.characters,
    required this.onCreateRelationship,
  }) : super(key: key);

  @override
  _CreateRelationshipDialogState createState() =>
      _CreateRelationshipDialogState();
}

class _CreateRelationshipDialogState extends State<CreateRelationshipDialog> {
  String? _character1;
  String? _character2;
  String _relationshipType = '';

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Create Relationship'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          DropdownButtonFormField<String>(
            value: _character1,
            items: widget.characters
                .map((c) =>
                    DropdownMenuItem(value: c['id'], child: Text(c['name']!)))
                .toList(),
            onChanged: (value) => setState(() => _character1 = value),
            decoration: InputDecoration(labelText: 'Character 1'),
          ),
          DropdownButtonFormField<String>(
            value: _character2,
            items: widget.characters
                .map((c) =>
                    DropdownMenuItem(value: c['id'], child: Text(c['name']!)))
                .toList(),
            onChanged: (value) => setState(() => _character2 = value),
            decoration: InputDecoration(labelText: 'Character 2'),
          ),
          TextField(
            onChanged: (value) => setState(() => _relationshipType = value),
            decoration: InputDecoration(labelText: 'Relationship Type'),
          ),
        ],
      ),
      actions: [
        TextButton(
          child: Text('Cancel'),
          onPressed: () => Navigator.of(context).pop(),
        ),
        ElevatedButton(
          child: Text('Create'),
          onPressed: _character1 != null &&
                  _character2 != null &&
                  _relationshipType.isNotEmpty
              ? () {
                  widget.onCreateRelationship(
                      _character1!, _character2!, _relationshipType);
                  Navigator.of(context).pop();
                }
              : null,
        ),
      ],
    );
  }
}
