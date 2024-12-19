import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
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
  final int _itemsPerPage = 10;
  List<dynamic> _displayedItems = [];
  bool _isLoadingMore = false;
  final ScrollController _scrollController = ScrollController();
  bool _mounted = true;
  bool _isExpanded = false;
  final TextEditingController _nameController = TextEditingController();
  final TextEditingController _descriptionController = TextEditingController();
  String _selectedType = 'lore';
  String _selectedSubtype = 'all';
  bool _isAdding = false;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _fetchCodexItems();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    _mounted = false;
    _scrollController.dispose();
    super.dispose();
  }

  void _safeSetState(VoidCallback fn) {
    if (_mounted && mounted) {
      setState(fn);
    }
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent * 0.8) {
      _loadMoreItems();
    }
  }

  void _loadMoreItems() {
    if (_isLoadingMore) return;

    final filteredItems = _getFilteredItems();
    final startIndex = _displayedItems.length;
    if (startIndex >= filteredItems.length) return;

    _safeSetState(() {
      _isLoadingMore = true;
    });

    Future.delayed(const Duration(milliseconds: 500), () {
      if (!_mounted) return;

      final newItems =
          filteredItems.skip(startIndex).take(_itemsPerPage).toList();

      _safeSetState(() {
        _displayedItems.addAll(newItems);
        _isLoadingMore = false;
      });
    });
  }

  void _resetDisplayedItems() {
    final filteredItems = _getFilteredItems();
    _safeSetState(() {
      _displayedItems = filteredItems.take(_itemsPerPage).toList();
    });
  }

  Future<void> _fetchCodexItems() async {
    if (!_mounted) return;

    setState(() {
      _isLoading = true;
      _error = '';
    });

    try {
      await Provider.of<AppState>(context, listen: false)
          .fetchCodexItems(widget.projectId);

      if (_mounted) {
        final appState = Provider.of<AppState>(context, listen: false);
        setState(() {
          _codexItems = appState.codexItems;
          _displayedItems = _codexItems.take(_itemsPerPage).toList();
          _isLoading = false;
        });
      }
    } catch (error) {
      if (_mounted) {
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
                        'lore', // Added 'lore' to the list
                        'faction' // Added 'faction' to the list
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
    // Show a single loading indicator
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Deleting selected items...')),
    );

    try {
      for (String itemId in _selectedItems) {
        await deleteCodexItem(context, itemId, showSnackbar: false);
      }

      // Show success message only once
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Successfully deleted selected items')),
      );

      setState(() {
        _selectedItems.clear();
        _isSelectionMode = false;
      });
      _fetchCodexItems();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error deleting items: $e')),
      );
    }
  }

  Future<void> deleteCodexItem(BuildContext context, String itemId,
      {bool showSnackbar = true}) async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.delete(
        Uri.parse('$apiUrl/codex-items/$itemId?project_id=${widget.projectId}'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        if (showSnackbar) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Codex item deleted successfully')),
          );
          Navigator.of(context).pop(); // Close the dialog
        }
        _fetchCodexItems();
      } else {
        final responseBody = json.decode(response.body);
        final error = responseBody['detail'] ?? 'Error deleting codex item';
        if (showSnackbar) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
                content:
                    Text('Error: $error (Status: ${response.statusCode})')),
          );
        }
        throw Exception(error);
      }
    } catch (e) {
      if (showSnackbar) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error deleting codex item: $e')),
        );
      }
      rethrow;
    }
  }

  void _toggleSelectAll(List<dynamic> items) {
    setState(() {
      if (_selectedItems.length == items.length) {
        // If all items are selected, deselect all
        _selectedItems.clear();
        _isSelectionMode = false;
      } else {
        // Select all items
        _selectedItems.addAll(items.map((item) => item['id'].toString()));
      }
    });
  }

  Future<void> _addCodexItem(BuildContext context) async {
    setState(() => _isAdding = true);

    try {
      final headers = await getAuthHeaders();
      final body = json.encode({
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
        _fetchCodexItems(); // Refresh the list
      } else {
        final error =
            json.decode(response.body)['error'] ?? 'Error adding codex item';
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
      _selectedSubtype = subtype ?? 'history';
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
                        items: const [
                          DropdownMenuItem(
                              value: 'history', child: Text('History')),
                          DropdownMenuItem(
                              value: 'culture', child: Text('Culture')),
                          DropdownMenuItem(
                              value: 'geography', child: Text('Geography')),
                        ],
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
                  onPressed: _isAdding ? null : () => _addCodexItem(context),
                  child: _isAdding
                      ? const CircularProgressIndicator()
                      : const Text('Add'),
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
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                _buildHeader(),
                _buildSearchAndFilters(),
                Expanded(
                  child: _error.isNotEmpty
                      ? _buildErrorState()
                      : _buildCodexList(_getFilteredItems()),
                ),
              ],
            ),
      floatingActionButton: Column(
        mainAxisAlignment: MainAxisAlignment.end,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          if (_isExpanded) ...[
            FloatingActionButton(
              heroTag: 'addLore',
              onPressed: () => _showAddCodexItemDialog(context, 'lore'),
              mini: true,
              child: const Icon(Icons.book),
            ),
            const SizedBox(height: 10),
            FloatingActionButton(
              heroTag: 'addWorldbuilding',
              onPressed: () =>
                  _showAddCodexItemDialog(context, 'worldbuilding'),
              mini: true,
              child: const Icon(Icons.public),
            ),
            const SizedBox(height: 10),
            FloatingActionButton(
              heroTag: 'addItem',
              onPressed: () => _showAddCodexItemDialog(context, 'item'),
              mini: true,
              child: const Icon(Icons.category),
            ),
            const SizedBox(height: 10),
            FloatingActionButton(
              heroTag: 'addCharacter',
              onPressed: () => _showAddCodexItemDialog(context, 'character'),
              mini: true,
              child: const Icon(Icons.person),
            ),
            const SizedBox(height: 10),
            FloatingActionButton(
              heroTag: 'addFaction',
              onPressed: () => _showAddCodexItemDialog(context, 'faction'),
              mini: true,
              child: const Icon(Icons.groups),
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

  Widget _buildHeader() {
    final filteredItems = _getFilteredItems();

    return Container(
      padding: const EdgeInsets.all(24),
      child: Row(
        children: [
          if (_isSelectionMode) ...[
            IconButton(
              icon: Icon(
                _selectedItems.length == filteredItems.length
                    ? Icons.check_box
                    : Icons.check_box_outline_blank,
              ),
              onPressed: () => _toggleSelectAll(filteredItems),
            ),
            Text('${_selectedItems.length} selected'),
            const Spacer(),
            IconButton(
              icon: const Icon(Icons.delete),
              onPressed: _selectedItems.isEmpty ? null : _deleteSelectedItems,
            ),
            IconButton(
              icon: const Icon(Icons.close),
              onPressed: () {
                setState(() {
                  _selectedItems.clear();
                  _isSelectionMode = false;
                });
              },
            ),
          ] else ...[
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
            onChanged: _handleSearch,
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
        _buildDropdownItem('faction', 'Factions', Icons.groups),
      ],
      onChanged: _handleTypeFilter,
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
    if (items.isEmpty) {
      return _buildEmptyState();
    }

    // Initialize displayed items if empty
    if (_displayedItems.isEmpty) {
      _displayedItems = items.take(_itemsPerPage).toList();
    }

    return ListView.builder(
      controller: _scrollController,
      itemCount: _displayedItems.length + (_isLoadingMore ? 1 : 0),
      padding: const EdgeInsets.all(16),
      itemBuilder: (context, index) {
        if (index == _displayedItems.length) {
          return _buildLoadingIndicator();
        }
        return _buildCodexCard(_displayedItems[index]);
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
      case 'faction':
        return Icons.groups;
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
      onChanged: _handleSubtypeFilter,
    );
  }

  void _handleSearch(String value) {
    _safeSetState(() {
      _searchController.text = value;
      _displayedItems.clear();
    });
    _resetDisplayedItems();
  }

  void _handleTypeFilter(String? newValue) {
    _safeSetState(() {
      _selectedTypeFilter = newValue!;
      _selectedSubtypeFilter = 'all';
      _displayedItems.clear();
    });
    _resetDisplayedItems();
  }

  void _handleSubtypeFilter(String? newValue) {
    _safeSetState(() {
      _selectedSubtypeFilter = newValue!;
      _displayedItems.clear();
    });
    _resetDisplayedItems();
  }

  Widget _buildLoadingIndicator() {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16),
      alignment: Alignment.center,
      child: const CircularProgressIndicator(),
    );
  }
}
