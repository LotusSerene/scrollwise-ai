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
  _EditRelationshipDialogState createState() => _EditRelationshipDialogState();
}

class _EditRelationshipDialogState extends State<EditRelationshipDialog> {
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
              'Between: ${widget.relationship.character1_name} and ${widget.relationship.character2_name}'),
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
              character1_id: widget.relationship.character1_id,
              character2_id: widget.relationship.character2_id,
              character1_name: widget.relationship.character1_name,
              character2_name: widget.relationship.character2_name,
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
