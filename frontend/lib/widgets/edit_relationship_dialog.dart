import 'package:flutter/material.dart';
import '../models/relationship.dart';

class EditRelationshipDialog extends StatefulWidget {
  final Relationship relationship;
  final Function(Relationship) onEditRelationship;

  const EditRelationshipDialog({
    Key? key,
    required this.relationship,
    required this.onEditRelationship,
  }) : super(key: key);

  @override
  EditRelationshipDialogState createState() => EditRelationshipDialogState();
}

class EditRelationshipDialogState extends State<EditRelationshipDialog> {
  late TextEditingController _relationshipTypeController;
  late TextEditingController _descriptionController;

  @override
  void initState() {
    super.initState();
    _relationshipTypeController =
        TextEditingController(text: widget.relationship.relationshipType);
    _descriptionController =
        TextEditingController(text: widget.relationship.description);
  }

  @override
  void dispose() {
    _relationshipTypeController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Edit Relationship'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
              'Between: ${widget.relationship.character1Name} and ${widget.relationship.character2Name}'),
          const SizedBox(height: 16),
          TextField(
            controller: _relationshipTypeController,
            decoration: const InputDecoration(labelText: 'Relationship Type'),
          ),
          TextField(
            controller: _descriptionController,
            decoration: const InputDecoration(labelText: 'Description'),
            maxLines: 3,
          ),
        ],
      ),
      actions: [
        TextButton(
          child: const Text('Cancel'),
          onPressed: () => Navigator.of(context).pop(),
        ),
        ElevatedButton(
          child: const Text('Save'),
          onPressed: () {
            final updatedRelationship = Relationship(
              id: widget.relationship.id,
              character1Id: widget.relationship.character1Id,
              character2Id: widget.relationship.character2Id,
              character1Name: widget.relationship.character1Name,
              character2Name: widget.relationship.character2Name,
              relationshipType: _relationshipTypeController.text,
              description: _descriptionController.text,
            );
            widget.onEditRelationship(updatedRelationship);
            Navigator.of(context).pop();
          },
        ),
      ],
    );
  }
}
