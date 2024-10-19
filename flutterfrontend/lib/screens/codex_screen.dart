import 'package:flutter/material.dart';
import '../components/codex.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';

class CodexScreen extends StatefulWidget {
  final String projectId;
  const CodexScreen({Key? key, required this.projectId}) : super(key: key);

  @override
  State<CodexScreen> createState() => _CodexScreenState();
}

class _CodexScreenState extends State<CodexScreen> {
  final TextEditingController _nameController = TextEditingController();
  final TextEditingController _descriptionController = TextEditingController();
  String _selectedType = 'lore';
  String _selectedSubtype = 'all';
  bool _isAdding = false;
  bool _isExpanded = false;

  Future<void> _addCodexItem(BuildContext context) async {
    setState(() => _isAdding = true);
    final appState = Provider.of<AppState>(context, listen: false);
    final token = appState.token;

    try {
      final headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      };
      final body = jsonEncode({
        'name': _nameController.text,
        'description': _descriptionController.text,
        'type': _selectedType,
        'subtype': _selectedSubtype == 'all' ? null : _selectedSubtype,
      });
      final response = await http.post(
        Uri.parse('$apiUrl/codex-items?project_id=${widget.projectId}'),
        headers: headers,
        body: body,
      );

      if (response.statusCode == 200) {
        // Codex item added successfully
        _nameController.clear();
        _descriptionController.clear();
        setState(() {
          _selectedType = 'lore';
          _selectedSubtype = 'all';
        });
        Navigator.of(context).pop(); // Close the dialog
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Codex item added successfully')),
        );
      } else {
        // Error adding codex item
        final error =
            jsonDecode(response.body)['error'] ?? 'Error adding codex item';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error)),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error adding codex item: $e')),
      );
    } finally {
      setState(() => _isAdding = false);
    }
  }

  void _showAddCodexItemDialog(BuildContext context, String type,
      {String? subtype}) {
    setState(() {
      _selectedType = type;
      _selectedSubtype = subtype ?? 'all';
    });
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              title: Text(
                  'Add ${type[0].toUpperCase() + type.substring(1)} Codex Item'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: _nameController,
                      decoration: const InputDecoration(labelText: 'Name'),
                    ),
                    TextField(
                      controller: _descriptionController,
                      decoration:
                          const InputDecoration(labelText: 'Description'),
                      maxLines: null,
                    ),
                    if (type == 'worldbuilding')
                      DropdownButtonFormField<String>(
                        value: _selectedSubtype,
                        onChanged: (String? newValue) {
                          setState(() {
                            _selectedSubtype = newValue!;
                          });
                        },
                        items: <String>['history', 'culture', 'geography']
                            .map<DropdownMenuItem<String>>((String value) {
                          return DropdownMenuItem<String>(
                            value: value,
                            child: Text(value),
                          );
                        }).toList(),
                        decoration: const InputDecoration(labelText: 'Subtype'),
                      ),
                  ],
                ),
              ),
              actions: <Widget>[
                TextButton(
                  child: const Text('Cancel'),
                  onPressed: () {
                    Navigator.of(context).pop();
                  },
                ),
                TextButton(
                  child: _isAdding
                      ? const CircularProgressIndicator()
                      : const Text('Add'),
                  onPressed: _isAdding ? null : () => _addCodexItem(context),
                ),
              ],
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Codex(projectId: widget.projectId),
      floatingActionButton: Column(
        mainAxisAlignment: MainAxisAlignment.end,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          if (_isExpanded) ...[
            FloatingActionButton(
              heroTag: 'addLore',
              onPressed: () => _showAddCodexItemDialog(context, 'lore'),
              child: const Icon(Icons.book),
              mini: true,
            ),
            const SizedBox(height: 10),
            FloatingActionButton(
              heroTag: 'addWorldbuilding',
              onPressed: () =>
                  _showAddCodexItemDialog(context, 'worldbuilding'),
              child: const Icon(Icons.public),
              mini: true,
            ),
            const SizedBox(height: 10),
            FloatingActionButton(
              heroTag: 'addItem',
              onPressed: () => _showAddCodexItemDialog(context, 'item'),
              child: const Icon(Icons.category),
              mini: true,
            ),
            const SizedBox(height: 10),
            FloatingActionButton(
              heroTag: 'addCharacter',
              onPressed: () => _showAddCodexItemDialog(context, 'character'),
              child: const Icon(Icons.person),
              mini: true,
            ),
            const SizedBox(height: 10),
          ],
          FloatingActionButton(
            heroTag: 'expandButton',
            onPressed: () {
              setState(() {
                _isExpanded = !_isExpanded;
              });
            },
            child: Icon(_isExpanded ? Icons.close : Icons.add),
          ),
        ],
      ),
    );
  }
}
