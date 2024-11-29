import 'package:flutter/material.dart';
import '../models/location_connection.dart';
import '../models/location.dart';

class LocationList extends StatefulWidget {
  final List<Location> locations;
  final List<LocationConnection> connections;
  final Function(Location) onEdit;
  final Function(String) onDelete;
  final Function(List<String>) onBatchDelete;
  final Function(String) onDeleteConnection;
  final Function(LocationConnection) onUpdateConnection;
  final int itemsPerPage = 10;

  const LocationList({
    Key? key,
    required this.locations,
    required this.connections,
    required this.onEdit,
    required this.onDelete,
    required this.onBatchDelete,
    required this.onDeleteConnection,
    required this.onUpdateConnection,
  }) : super(key: key);

  @override
  _LocationListState createState() => _LocationListState();
}

class _LocationListState extends State<LocationList> {
  Set<String> selectedLocations = {};
  bool isSelectionMode = false;
  bool _mounted = true;
  bool _isLoading = false;
  final ScrollController _scrollController = ScrollController();
  int _currentPage = 0;
  final List<Location> _displayedLocations = [];

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _loadMoreItems();
  }

  @override
  void dispose() {
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
    if (_isLoading) return;

    _safeSetState(() {
      _isLoading = true;
    });

    // Simulate loading delay
    Future.delayed(const Duration(milliseconds: 500), () {
      if (!_mounted) return;

      final startIndex = _currentPage * widget.itemsPerPage;
      final newItems =
          widget.locations.skip(startIndex).take(widget.itemsPerPage).toList();

      _safeSetState(() {
        _displayedLocations.addAll(newItems);
        _currentPage++;
        _isLoading = false;
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    if (widget.locations.isEmpty) {
      return _buildEmptyState();
    }

    return ConstrainedBox(
      constraints: const BoxConstraints(maxHeight: 800),
      child: Stack(
        children: [
          if (isSelectionMode)
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: _buildSelectionControls(),
            ),
          Padding(
            padding: EdgeInsets.only(top: isSelectionMode ? 60.0 : 0),
            child: ListView.builder(
              shrinkWrap: true,
              controller: _scrollController,
              itemCount: _displayedLocations.length + (_isLoading ? 1 : 0),
              itemBuilder: (context, index) {
                if (index == _displayedLocations.length) {
                  return _buildLoadingIndicator();
                }
                return _buildLocationCard(_displayedLocations[index]);
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Card(
      child: Container(
        padding: const EdgeInsets.all(24),
        alignment: Alignment.center,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.location_off,
              size: 48,
              color: Theme.of(context).colorScheme.secondary,
            ),
            const SizedBox(height: 16),
            Text(
              'No locations created yet',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLoadingIndicator() {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16),
      alignment: Alignment.center,
      child: const CircularProgressIndicator(),
    );
  }

  Widget _buildSelectionControls() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          TextButton.icon(
            icon: const Icon(Icons.select_all),
            label: const Text('Select All'),
            onPressed: _selectAll,
          ),
          TextButton.icon(
            icon: const Icon(Icons.deselect),
            label: const Text('Deselect All'),
            onPressed: _deselectAll,
          ),
          FilledButton.icon(
            icon: const Icon(Icons.delete),
            label: Text('Delete (${selectedLocations.length})'),
            onPressed: selectedLocations.isEmpty ? null : _deleteSelected,
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
              foregroundColor: Theme.of(context).colorScheme.onError,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLocationCard(Location location) {
    final locationConnections = widget.connections
        .where((conn) =>
            conn.location1Id == location.id || conn.location2Id == location.id)
        .toList();

    return Card(
      elevation: 2,
      margin: const EdgeInsets.symmetric(vertical: 8),
      child: InkWell(
        onLongPress: () {
          _safeSetState(() {
            isSelectionMode = true;
            selectedLocations.add(location.id);
          });
        },
        child: Theme(
          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
          child: ExpansionTile(
            leading: isSelectionMode
                ? Checkbox(
                    value: selectedLocations.contains(location.id),
                    onChanged: (bool? value) {
                      _safeSetState(() {
                        if (value == true) {
                          selectedLocations.add(location.id);
                        } else {
                          selectedLocations.remove(location.id);
                        }
                      });
                    },
                  )
                : CircleAvatar(
                    backgroundColor:
                        Theme.of(context).colorScheme.secondaryContainer,
                    child: Icon(
                      Icons.place,
                      color: Theme.of(context).colorScheme.onSecondaryContainer,
                    ),
                  ),
            title: Text(
              location.name,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            subtitle: Text(
              location.coordinates ?? 'No coordinates specified',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            trailing: isSelectionMode
                ? null
                : Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      IconButton(
                        icon: const Icon(Icons.edit),
                        onPressed: () => widget.onEdit(location),
                      ),
                      IconButton(
                        icon: const Icon(Icons.delete),
                        onPressed: () => widget.onDelete(location.id),
                      ),
                    ],
                  ),
            children: [
              Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      location.description,
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    if (location.significance != null) ...[
                      const SizedBox(height: 16),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Theme.of(context)
                              .colorScheme
                              .secondaryContainer
                              .withOpacity(0.5),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              Icons.star,
                              size: 20,
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSecondaryContainer,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                location.significance!,
                                style: TextStyle(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSecondaryContainer,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    if (locationConnections.isNotEmpty &&
                        widget.connections.isNotEmpty) ...[
                      const SizedBox(height: 24),
                      Text(
                        'Connected Locations',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      const SizedBox(height: 8),
                      ...locationConnections.map((conn) {
                        final connectedLocation = widget.locations.firstWhere(
                          (l) =>
                              l.id ==
                              (conn.location1Id == location.id
                                  ? conn.location2Id
                                  : conn.location1Id),
                        );
                        return _buildConnectionCard(conn, connectedLocation);
                      }),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildConnectionCard(
      LocationConnection conn, Location connectedLocation) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.compare_arrows,
                  size: 16,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    connectedLocation.name,
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
                PopupMenuButton(
                  itemBuilder: (context) => [
                    PopupMenuItem(
                      child: const Text('Edit'),
                      onTap: () => _editLocationConnection(conn),
                    ),
                    PopupMenuItem(
                      child: const Text('Delete'),
                      onTap: () => _deleteLocationConnection(conn.id),
                    ),
                  ],
                ),
              ],
            ),
            ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.route,
                      size: 16,
                      color: Theme.of(context).colorScheme.onPrimaryContainer,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        conn.travelRoute,
                        style: TextStyle(
                          color:
                              Theme.of(context).colorScheme.onPrimaryContainer,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.secondaryContainer,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.people,
                      size: 16,
                      color: Theme.of(context).colorScheme.onSecondaryContainer,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        conn.culturalExchange,
                        style: TextStyle(
                          color: Theme.of(context)
                              .colorScheme
                              .onSecondaryContainer,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _editLocationConnection(LocationConnection connection) async {
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Edit Connection'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              decoration: const InputDecoration(labelText: 'Travel Route'),
              controller: TextEditingController(text: connection.travelRoute),
              maxLines: 2,
            ),
            const SizedBox(height: 16),
            TextField(
              decoration: const InputDecoration(labelText: 'Cultural Exchange'),
              controller:
                  TextEditingController(text: connection.culturalExchange),
              maxLines: 3,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              // Handle save
              Navigator.pop(context);
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );

    if (result != null) {
      widget.onUpdateConnection(connection);
    }
  }

  void _selectAll() {
    _safeSetState(() {
      selectedLocations = widget.locations.map((e) => e.id).toSet();
    });
  }

  void _deselectAll() {
    _safeSetState(() {
      selectedLocations.clear();
      isSelectionMode = false;
    });
  }

  Future<void> _deleteSelected() async {
    final bool confirm = await showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Selected Locations'),
        content: Text(
            'Are you sure you want to delete ${selectedLocations.length} locations?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
              foregroundColor: Theme.of(context).colorScheme.onError,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      await widget.onBatchDelete(selectedLocations.toList());
      _safeSetState(() {
        selectedLocations.clear();
        isSelectionMode = false;
      });
    }
  }

  void _deleteLocationConnection(String connectionId) {
    widget.onDeleteConnection(connectionId);
  }

  Widget _buildLocationConnectionsList(Location location) {
    final locationConnections = widget.connections
        .where((conn) =>
            conn.location1Id == location.id || conn.location2Id == location.id)
        .toList();

    if (locationConnections.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Divider(),
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8.0),
          child: Text(
            'Connected Locations',
            style: Theme.of(context).textTheme.titleSmall,
          ),
        ),
        ListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: locationConnections.length,
          itemBuilder: (context, index) {
            final conn = locationConnections[index];
            final connectedLocation = widget.locations.firstWhere(
              (l) =>
                  l.id ==
                  (conn.location1Id == location.id
                      ? conn.location2Id
                      : conn.location1Id),
            );

            return Card(
              margin: const EdgeInsets.symmetric(vertical: 4),
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              child: ListTile(
                leading: const Icon(Icons.compare_arrows),
                title: Text(connectedLocation.name),
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (conn.travelRoute.isNotEmpty)
                      Text('Travel: ${conn.travelRoute}'),
                    if (conn.culturalExchange.isNotEmpty)
                      Text('Exchange: ${conn.culturalExchange}'),
                  ],
                ),
                trailing: PopupMenuButton(
                  itemBuilder: (context) => [
                    PopupMenuItem(
                      child: const Text('Edit'),
                      onTap: () => _editLocationConnection(conn),
                    ),
                    PopupMenuItem(
                      child: const Text('Delete'),
                      onTap: () => _showDeleteConnectionDialog(conn.id),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ],
    );
  }

  Future<void> _showDeleteConnectionDialog(String connectionId) async {
    final bool confirm = await showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Connection'),
        content: const Text('Are you sure you want to delete this connection?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
              foregroundColor: Theme.of(context).colorScheme.onError,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      widget.onDeleteConnection(connectionId);
    }
  }
}
