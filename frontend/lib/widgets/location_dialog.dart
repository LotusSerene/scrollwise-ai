import 'package:flutter/material.dart';
import '../models/location.dart';

class LocationDialog extends StatefulWidget {
  final Location? location;

  const LocationDialog({Key? key, this.location}) : super(key: key);

  @override
  State<LocationDialog> createState() => _LocationDialogState();
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
    return Dialog(
      child: Container(
        constraints: const BoxConstraints(maxWidth: 500),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  CircleAvatar(
                    backgroundColor:
                        Theme.of(context).colorScheme.secondaryContainer,
                    child: Icon(
                      Icons.edit_location_alt, // Updated icon
                      color: Theme.of(context).colorScheme.onSecondaryContainer,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Text(
                    widget.location == null
                        ? 'Create Location'
                        : 'Edit Location',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                ],
              ),
              const SizedBox(height: 24),
              TextField(
                controller: _nameController,
                decoration: InputDecoration(
                  labelText: 'Name',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  prefixIcon: const Icon(Icons.label),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _descriptionController,
                decoration: InputDecoration(
                  labelText: 'Description',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  prefixIcon: const Icon(Icons.description),
                ),
                maxLines: 3,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _coordinatesController,
                decoration: InputDecoration(
                  labelText: 'Coordinates (optional)',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  prefixIcon: const Icon(Icons.map),
                  hintText: 'e.g., 40.7128° N, 74.0060° W',
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _significanceController,
                decoration: InputDecoration(
                  labelText: 'Significance',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  prefixIcon: const Icon(Icons.star),
                ),
                maxLines: 2,
              ),
              const SizedBox(height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Cancel'),
                  ),
                  const SizedBox(width: 8),
                  FilledButton.icon(
                    icon: const Icon(Icons.save),
                    label: const Text('Save'),
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
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
