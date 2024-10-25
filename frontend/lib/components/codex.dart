import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';

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
      setState(() {
        isUpdating = true;
      });

      try {
        final headers = await getAuthHeaders();
        final response = await http.put(
          Uri.parse(
              '$apiUrl/codex-items/${item['id']}?project_id=${widget.projectId}'),
          headers: headers,
          body: json.encode({
            'name': nameController.text,
            'description': descriptionController.text,
            'type': selectedType,
            'subtype': selectedSubtype == 'all' ? null : selectedSubtype,
          }),
        );

        if (response.statusCode == 200) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Codex item updated successfully')),
          );
          Navigator.of(context).pop(); // Close the dialog
          _fetchCodexItems(); // Refresh the codex items
        } else {
          final responseBody = json.decode(response.body);
          final error = responseBody['detail'] ?? 'Error updating codex item';
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
                content:
                    Text('Error: $error (Status: ${response.statusCode})')),
          );
        }
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error updating codex item: $e')),
        );
      } finally {
        setState(() {
          isUpdating = false;
        });
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
                        'lore' // Added 'lore' to the list
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

    final filteredItems = _getFilteredItems();

    return Column(
      children: [
        _buildHeader(),
        _buildSearchAndFilters(),
        Expanded(
          child: _error.isNotEmpty
              ? _buildErrorState()
              : _buildCodexList(filteredItems),
        ),
      ],
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(24),
      child: Row(
        children: [
          Icon(
            Icons.book,
            size: 32,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(width: 16),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Codex',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              Text(
                'Organize your world\'s knowledge',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context)
                          .colorScheme
                          .onSurface
                          .withOpacity(0.6),
                    ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSearchAndFilters() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(16)),
        boxShadow: [
          BoxShadow(
            color: Theme.of(context).shadowColor.withOpacity(0.1),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          TextField(
            controller: _searchController,
            decoration: InputDecoration(
              hintText: 'Search codex items...',
              prefixIcon: const Icon(Icons.search),
              suffixIcon: _searchController.text.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear),
                      onPressed: () {
                        _searchController.clear();
                        setState(() {});
                      },
                    )
                  : null,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              filled: true,
              fillColor: Theme.of(context).colorScheme.surface,
            ),
            onChanged: (value) => setState(() {}),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(child: _buildTypeDropdown()),
              if (_selectedTypeFilter == 'worldbuilding') ...[
                const SizedBox(width: 16),
                Expanded(child: _buildSubtypeDropdown()),
              ],
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildTypeDropdown() {
    return DropdownButtonFormField<String>(
      value: _selectedTypeFilter,
      decoration: InputDecoration(
        labelText: 'Type',
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      ),
      items: [
        _buildDropdownItem('all', 'All Types', Icons.category),
        _buildDropdownItem('lore', 'Lore', Icons.book),
        _buildDropdownItem('worldbuilding', 'World Building', Icons.public),
        _buildDropdownItem('item', 'Items', Icons.inventory_2),
        _buildDropdownItem('character', 'Characters', Icons.person),
      ],
      onChanged: (String? newValue) {
        setState(() {
          _selectedTypeFilter = newValue!;
          _selectedSubtypeFilter = 'all';
        });
      },
    );
  }

  DropdownMenuItem<String> _buildDropdownItem(
      String value, String label, IconData icon) {
    return DropdownMenuItem<String>(
      value: value,
      child: Row(
        children: [
          Icon(icon, size: 20),
          const SizedBox(width: 8),
          Text(label),
        ],
      ),
    );
  }

  Widget _buildCodexList(List<dynamic> items) {
    return items.isEmpty
        ? _buildEmptyState()
        : ListView.builder(
            itemCount: items.length,
            padding: const EdgeInsets.all(16),
            itemBuilder: (context, index) {
              final item = items[index];
              return _buildCodexCard(item);
            },
          );
  }

  Widget _buildCodexCard(dynamic item) {
    final isSelected = _selectedItems.contains(item['id']);
    final IconData typeIcon = _getTypeIcon(item['type']);

    return Card(
      elevation: 2,
      margin: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: isSelected
            ? BorderSide(
                color: Theme.of(context).colorScheme.primary,
                width: 2,
              )
            : BorderSide.none,
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: _isSelectionMode
            ? () => _toggleItemSelection(item['id'])
            : () => _showCodexItemDetails(context, item),
        onLongPress: () => _toggleItemSelection(item['id']),
        child: Container(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              if (_isSelectionMode)
                Padding(
                  padding: const EdgeInsets.only(right: 16),
                  child: Checkbox(
                    value: isSelected,
                    onChanged: (_) => _toggleItemSelection(item['id']),
                  ),
                ),
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primary.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  typeIcon,
                  color: Theme.of(context).colorScheme.primary,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item['name'],
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                    if (item['description'].isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        item['description'],
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurface
                                  .withOpacity(0.7),
                            ),
                      ),
                    ],
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        _buildChip(item['type']),
                        if (item['subtype'] != null) ...[
                          const SizedBox(width: 8),
                          _buildChip(item['subtype']),
                        ],
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildChip(String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.secondaryContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: Theme.of(context).colorScheme.onSecondaryContainer,
            ),
      ),
    );
  }

  IconData _getTypeIcon(String type) {
    switch (type) {
      case 'lore':
        return Icons.book;
      case 'worldbuilding':
        return Icons.public;
      case 'item':
        return Icons.inventory_2;
      case 'character':
        return Icons.person;
      default:
        return Icons.article;
    }
  }

  Widget _buildErrorState() {
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

  Widget _buildEmptyState() {
    return Center(
      child: Text('No items found.',
          style: Theme.of(context).textTheme.bodyMedium),
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
          const SnackBar(content: Text('Codex item deleted successfully')),
        );
        _fetchCodexItems();
      } else {
        final responseBody = json.decode(response.body);
        final error = responseBody['detail'] ?? 'Error deleting codex item';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text('Error: $error (Status: ${response.statusCode})')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error deleting codex item: $e')),
      );
    }
  }

  Widget _buildSubtypeDropdown() {
    return DropdownButtonFormField<String>(
      value: _selectedSubtypeFilter,
      decoration: InputDecoration(
        labelText: 'Subtype',
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      ),
      items: [
        _buildDropdownItem('all', 'All Subtypes', Icons.category),
        _buildDropdownItem('history', 'History', Icons.history),
        _buildDropdownItem('culture', 'Culture', Icons.people),
        _buildDropdownItem('geography', 'Geography', Icons.landscape),
      ],
      onChanged: (String? newValue) {
        setState(() {
          _selectedSubtypeFilter = newValue!;
        });
      },
    );
  }
}
