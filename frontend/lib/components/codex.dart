import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:typed_data';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';

class Codex extends StatefulWidget {
  final String projectId;

  const Codex({Key? key, required this.projectId}) : super(key: key);

  @override
  State<Codex> createState() => _CodexState();
}

class _CodexState extends State<Codex> {
  List<dynamic> _codexItems = [];
  String _selectedTypeFilter = 'all';
  String _selectedSubtypeFilter = 'all';
  final TextEditingController _searchController = TextEditingController();
  bool _isLoading = true;
  String _error = '';
  final Set<String> _selectedItems = {};
  bool _isSelectionMode = false;

  @override
  void initState() {
    super.initState();
    _fetchCodexItems();
  }

  Future<void> _fetchCodexItems() async {
    setState(() {
      _isLoading = true;
      _error = '';
    });

    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/codex-items?project_id=${widget.projectId}'),
        headers: headers,
      );
      final jsonResponse = json.decode(utf8.decode(response.bodyBytes));
      if (response.statusCode == 200 && !jsonResponse.containsKey('error')) {
        if (mounted) {
          setState(() {
            _codexItems = jsonResponse['codex_items'];
            _isLoading = false;
          });
        }
      } else {
        if (mounted) {
          setState(() {
            _error = jsonResponse['error'] ?? 'Error fetching codex items';
            _isLoading = false;
          });
        }
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = 'Error fetching codex items: $error';
          _isLoading = false;
        });
      }
    }
  }

  List<dynamic> _getFilteredItems() {
    return _codexItems.where((item) {
      bool matchesFilter =
          _selectedTypeFilter == 'all' || item['type'] == _selectedTypeFilter;
      if (_selectedTypeFilter == 'worldbuilding') {
        matchesFilter = matchesFilter &&
            (_selectedSubtypeFilter == 'all' ||
                item['subtype'] == _selectedSubtypeFilter);
      }
      bool matchesSearch = _searchController.text.isEmpty ||
          item['name']
              .toLowerCase()
              .contains(_searchController.text.toLowerCase()) ||
          item['description']
              .toLowerCase()
              .contains(_searchController.text.toLowerCase());
      return matchesFilter && matchesSearch;
    }).toList();
  }

  void _showCodexItemDetails(BuildContext context, dynamic item) {
    final TextEditingController nameController =
        TextEditingController(text: item['name']);
    final TextEditingController descriptionController =
        TextEditingController(text: item['description']);
    String selectedType = item['type'];
    String selectedSubtype = item['subtype'] ?? 'all';
    bool isUpdating = false;

    Future<void> updateCodexItem(BuildContext context) async {
      setState(() => isUpdating = true);
      final appState = Provider.of<AppState>(context, listen: false);
      final token = appState.token;

      try {
        final headers = {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $token',
        };
        final body = jsonEncode({
          'name': nameController.text,
          'description': descriptionController.text,
          'type': selectedType,
          'subtype': selectedSubtype == 'all' ? null : selectedSubtype,
        });
        final response = await http.put(
          Uri.parse(
              '$apiUrl/codex-items/${item['id']}?project_id=${widget.projectId}'),
          headers: headers,
          body: utf8.encode(json.encode(body)),
        );

        if (response.statusCode == 200) {
          // Codex item updated successfully
          Navigator.of(context).pop(); // Close the dialog
          _fetchCodexItems(); // Refresh the list
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Codex item updated successfully')),
          );
        } else {
          // Error updating codex item
          final error =
              jsonDecode(response.body)['error'] ?? 'Error updating codex item';
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(error)),
          );
        }
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error updating codex item: $e')),
        );
      } finally {
        setState(() => isUpdating = false);
      }
    }

    showDialog(
      context: context,
      builder: (BuildContext context) {
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              title: Text(item['name']),
              content: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    TextField(
                      controller: nameController,
                      decoration: const InputDecoration(labelText: 'Name'),
                    ),
                    TextField(
                      controller: descriptionController,
                      decoration:
                          const InputDecoration(labelText: 'Description'),
                      maxLines: null,
                    ),
                    DropdownButtonFormField<String>(
                      value: selectedType,
                      onChanged: (String? newValue) {
                        setState(() {
                          selectedType = newValue!;
                          if (newValue != 'worldbuilding') {
                            selectedSubtype = 'all';
                          }
                        });
                      },
                      items: <String>[
                        'worldbuilding',
                        'character',
                        'item',
                        'lore'
                      ].map<DropdownMenuItem<String>>((String value) {
                        return DropdownMenuItem<String>(
                          value: value,
                          child: Text(value),
                        );
                      }).toList(),
                      decoration: const InputDecoration(labelText: 'Type'),
                    ),
                    if (selectedType == 'worldbuilding')
                      DropdownButtonFormField<String>(
                        value: selectedSubtype,
                        onChanged: (String? newValue) {
                          setState(() {
                            selectedSubtype = newValue!;
                          });
                        },
                        items: <String>[
                          'all',
                          'history',
                          'culture',
                          'geography'
                        ].map<DropdownMenuItem<String>>((String value) {
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
                  onPressed: () => deleteCodexItem(context, item['id']),
                  style: TextButton.styleFrom(
                    foregroundColor: Colors.red,
                  ),
                  child: const Text('Delete'),
                ),
                TextButton(
                  child: const Text('Cancel'),
                  onPressed: () {
                    Navigator.of(context).pop();
                  },
                ),
                TextButton(
                  onPressed: isUpdating ? null : () => updateCodexItem(context),
                  child: isUpdating
                      ? const CircularProgressIndicator()
                      : const Text('Update'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  void _toggleItemSelection(String itemId) {
    setState(() {
      if (_selectedItems.contains(itemId)) {
        _selectedItems.remove(itemId);
      } else {
        _selectedItems.add(itemId);
      }
      _isSelectionMode = _selectedItems.isNotEmpty;
    });
  }

  Future<void> _deleteSelectedItems() async {
    for (String itemId in _selectedItems) {
      await deleteCodexItem(context, itemId);
    }
    setState(() {
      _selectedItems.clear();
      _isSelectionMode = false;
    });
    _fetchCodexItems();
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error.isNotEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(_error, style: const TextStyle(color: Colors.red)),
            ElevatedButton(
              onPressed: _fetchCodexItems,
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    final filteredItems = _getFilteredItems();

    return Stack(
      children: [
        Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: TextField(
                controller: _searchController,
                decoration: InputDecoration(
                  hintText: 'Search codex items...',
                  prefixIcon: const Icon(Icons.search),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
                onChanged: (value) => setState(() {}),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  Expanded(
                    child: DropdownButtonFormField<String>(
                      value: _selectedTypeFilter,
                      onChanged: (String? newValue) {
                        setState(() {
                          _selectedTypeFilter = newValue!;
                          _selectedSubtypeFilter = 'all';
                        });
                      },
                      items: <String>[
                        'all',
                        'lore',
                        'worldbuilding',
                        'item',
                        'character'
                      ].map<DropdownMenuItem<String>>((String value) {
                        return DropdownMenuItem<String>(
                          value: value,
                          child: Text(value),
                        );
                      }).toList(),
                      decoration: InputDecoration(
                        labelText: 'Type',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                        ),
                      ),
                    ),
                  ),
                  if (_selectedTypeFilter == 'worldbuilding') ...[
                    const SizedBox(width: 16),
                    Expanded(
                      child: DropdownButtonFormField<String>(
                        value: _selectedSubtypeFilter,
                        onChanged: (String? newValue) {
                          setState(() {
                            _selectedSubtypeFilter = newValue!;
                          });
                        },
                        items: <String>[
                          'all',
                          'history',
                          'culture',
                          'geography'
                        ].map<DropdownMenuItem<String>>((String value) {
                          return DropdownMenuItem<String>(
                            value: value,
                            child: Text(value),
                          );
                        }).toList(),
                        decoration: InputDecoration(
                          labelText: 'Subtype',
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                          ),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: ListView.builder(
                itemCount: filteredItems.length,
                padding: const EdgeInsets.all(16),
                itemBuilder: (context, index) {
                  final item = filteredItems[index];
                  final isSelected = _selectedItems.contains(item['id']);
                  return Card(
                    elevation: 3,
                    margin: const EdgeInsets.symmetric(vertical: 8),
                    child: ListTile(
                      title: Text(
                        item['name'],
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 18,
                        ),
                      ),
                      subtitle: Text(
                        item['description'],
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      onTap: _isSelectionMode
                          ? () => _toggleItemSelection(item['id'])
                          : () => _showCodexItemDetails(context, item),
                      onLongPress: () => _toggleItemSelection(item['id']),
                      tileColor:
                          isSelected ? Colors.blue.withOpacity(0.1) : null,
                      leading: _isSelectionMode
                          ? Checkbox(
                              value: isSelected,
                              onChanged: (_) =>
                                  _toggleItemSelection(item['id']),
                            )
                          : null,
                    ),
                  );
                },
              ),
            ),
          ],
        ),
        if (_isSelectionMode)
          Positioned(
            bottom: 16,
            right: 16,
            child: FloatingActionButton.extended(
              onPressed: _deleteSelectedItems,
              label: const Text('Delete Selected'),
              icon: const Icon(Icons.delete),
              backgroundColor: Colors.red,
            ),
          ),
      ],
    );
  }

  Future<void> deleteCodexItem(BuildContext context, String itemId) async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.delete(
        Uri.parse('$apiUrl/codex-items/$itemId?project_id=${widget.projectId}'),
        headers: headers,
      );
      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Codex item deleted successfully'),
          ),
        );
      } else {
        final error =
            jsonDecode(response.body)['error'] ?? 'Error deleting codex item';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error)),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error deleting codex item: $e')),
      );
    }
  }
}
