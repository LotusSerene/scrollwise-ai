import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';

class Codex extends StatefulWidget {
  const Codex({Key? key}) : super(key: key);

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
        Uri.parse('$apiUrl/codex-items'),
        headers: headers,
      );
      final jsonResponse = json.decode(response.body);
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
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text(item['name']),
          content: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Type: ${item['type']}'),
                if (item['subtype'] != null) Text('Subtype: ${item['subtype']}'),
                Text('Description: ${item['description']}'),
                // Add other fields as needed
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(
              child: const Text('Close'),
              onPressed: () {
                Navigator.of(context).pop();
              },
            ),
          ],
        );
      },
    );
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

    return Column(
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
                    items: <String>['all', 'history', 'culture', 'geography']
                        .map<DropdownMenuItem<String>>((String value) {
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
                  onTap: () => _showCodexItemDetails(context, item),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}
