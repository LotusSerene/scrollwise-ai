import 'package:flutter/material.dart';
import '../models/location.dart';

class LocationDialog extends StatefulWidget {
  final Location? location;

  const LocationDialog({Key? key, this.location}) : super(key: key);

  @override
  _LocationDialogState createState() => _LocationDialogState();
}

class _LocationDialogState extends State<LocationDialog> {
  late TextEditingController _nameController;
  late TextEditingController _descriptionController;
  late TextEditingController _coordinatesController;
  late TextEditingController _significanceController;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.location?.name ?? '');
    _descriptionController =
        TextEditingController(text: widget.location?.description ?? '');
    _coordinatesController =
        TextEditingController(text: widget.location?.coordinates ?? '');
    _significanceController =
        TextEditingController(text: widget.location?.significance ?? '');
  }

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    _coordinatesController.dispose();
    _significanceController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title:
          Text(widget.location == null ? 'Create Location' : 'Edit Location'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _nameController,
              decoration: const InputDecoration(labelText: 'Name'),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _descriptionController,
              decoration: const InputDecoration(labelText: 'Description'),
              maxLines: 3,
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _coordinatesController,
              decoration:
                  const InputDecoration(labelText: 'Coordinates (optional)'),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _significanceController,
              decoration: const InputDecoration(labelText: 'Significance'),
              maxLines: 2,
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        TextButton(
          onPressed: () {
            final result = {
              'name': _nameController.text,
              'description': _descriptionController.text,
              'coordinates': _coordinatesController.text.isEmpty
                  ? null
                  : _coordinatesController.text,
              'significance': _significanceController.text,
            };
            Navigator.pop(context, result);
          },
          child: const Text('Save'),
        ),
      ],
    );
  }
}
