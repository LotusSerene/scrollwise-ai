import 'package:flutter/material.dart';

class CreateRelationshipDialog extends StatefulWidget {
  final List<Map<String, dynamic>> characters;
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
      title: const Text('Create Relationship'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          DropdownButtonFormField<String>(
            value: _character1,
            items: widget.characters
                .map((c) => DropdownMenuItem<String>(
                    value: c['id'].toString(),
                    child: Text(c['name'].toString())))
                .toList(),
            onChanged: (value) => setState(() => _character1 = value),
            decoration: const InputDecoration(labelText: 'Character 1'),
          ),
          DropdownButtonFormField<String>(
            value: _character2,
            items: widget.characters
                .map((c) => DropdownMenuItem<String>(
                    value: c['id'].toString(),
                    child: Text(c['name'].toString())))
                .toList(),
            onChanged: (value) => setState(() => _character2 = value),
            decoration: const InputDecoration(labelText: 'Character 2'),
          ),
          TextField(
            onChanged: (value) => setState(() => _relationshipType = value),
            decoration: const InputDecoration(labelText: 'Relationship Type'),
          ),
        ],
      ),
      actions: [
        TextButton(
          child: const Text('Cancel'),
          onPressed: () => Navigator.of(context).pop(),
        ),
        ElevatedButton(
          onPressed: _character1 != null &&
                  _character2 != null &&
                  _relationshipType.isNotEmpty
              ? () {
                  widget.onCreateRelationship(
                      _character1!, _character2!, _relationshipType);
                  Navigator.of(context).pop();
                }
              : null,
          child: const Text('Create'),
        ),
      ],
    );
  }
}
