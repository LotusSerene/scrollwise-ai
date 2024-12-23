import 'package:flutter/material.dart';
import '../models/event_connection.dart';
import '../models/event.dart';

class EventList extends StatefulWidget {
  final List<Event> events;
  final List<EventConnection> connections;
  final Function(Event) onEdit;
  final Function(String) onDelete;
  final Function(String) onDeleteConnection;
  final Function(EventConnection) onUpdateConnection;
  final int itemsPerPage = 10;

  const EventList({
    Key? key,
    required this.events,
    required this.connections,
    required this.onEdit,
    required this.onDelete,
    required this.onDeleteConnection,
    required this.onUpdateConnection,
  }) : super(key: key);

  @override
  State<EventList> createState() => _EventListState();
}

class _EventListState extends State<EventList> {
  Set<String> selectedEvents = {};
  bool isSelectionMode = false;
  bool _mounted = true;
  bool _isLoading = false;
  final ScrollController _scrollController = ScrollController();
  int _currentPage = 0;
  final List<Event> _displayedEvents = [];

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
          widget.events.skip(startIndex).take(widget.itemsPerPage).toList();

      _safeSetState(() {
        _displayedEvents.addAll(newItems);
        _currentPage++;
        _isLoading = false;
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    if (widget.events.isEmpty) {
      return _buildEmptyState();
    }

    return Stack(
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
            controller: _scrollController,
            itemCount: _displayedEvents.length + (_isLoading ? 1 : 0),
            itemBuilder: (context, index) {
              if (index == _displayedEvents.length) {
                return _buildLoadingIndicator();
              }
              return _buildEventCard(_displayedEvents[index]);
            },
          ),
        ),
      ],
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
              Icons.event_busy,
              size: 48,
              color: Theme.of(context).colorScheme.secondary,
            ),
            const SizedBox(height: 16),
            Text(
              'No events created yet',
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
            label: Text('Delete (${selectedEvents.length})'),
            onPressed: selectedEvents.isEmpty ? null : _deleteSelected,
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
              foregroundColor: Theme.of(context).colorScheme.onError,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEventCard(Event event) {
    return InkWell(
      onLongPress: () {
        setState(() {
          isSelectionMode = true;
          selectedEvents.add(event.id);
        });
      },
      child: Card(
        elevation: 2,
        margin: const EdgeInsets.symmetric(vertical: 8),
        child: Stack(
          children: [
            Theme(
              data:
                  Theme.of(context).copyWith(dividerColor: Colors.transparent),
              child: ExpansionTile(
                leading: isSelectionMode
                    ? Checkbox(
                        value: selectedEvents.contains(event.id),
                        onChanged: (bool? value) {
                          setState(() {
                            if (value == true) {
                              selectedEvents.add(event.id);
                            } else {
                              selectedEvents.remove(event.id);
                            }
                          });
                        },
                      )
                    : CircleAvatar(
                        backgroundColor:
                            Theme.of(context).colorScheme.primaryContainer,
                        child: Text(
                          event.title.substring(0, 1).toUpperCase(),
                          style: TextStyle(
                            color: Theme.of(context)
                                .colorScheme
                                .onPrimaryContainer,
                          ),
                        ),
                      ),
                title: Text(
                  event.title,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                subtitle: Text(
                  event.date.toString(),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                trailing: isSelectionMode
                    ? null
                    : Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          IconButton(
                            icon: const Icon(Icons.edit),
                            onPressed: () => widget.onEdit(event),
                          ),
                          IconButton(
                            icon: const Icon(Icons.delete),
                            onPressed: () => widget.onDelete(event.id),
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
                          event.description,
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                        if (event.impact != null) ...[
                          const SizedBox(height: 8),
                          Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: Theme.of(context)
                                  .colorScheme
                                  .secondaryContainer,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Row(
                              children: [
                                Icon(
                                  Icons.change_history,
                                  size: 16,
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSecondaryContainer,
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    event.impact!,
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
                  _buildEventConnectionsList(event),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEventConnectionsList(Event event) {
    final eventConnections = widget.connections
        .where((conn) => conn.event1Id == event.id || conn.event2Id == event.id)
        .toList();

    if (eventConnections.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Divider(),
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8.0),
          child: Text(
            'Connected Events',
            style: Theme.of(context).textTheme.titleSmall,
          ),
        ),
        ListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: eventConnections.length,
          itemBuilder: (context, index) {
            final conn = eventConnections[index];
            final connectedEvent = widget.events.firstWhere(
              (e) =>
                  e.id ==
                  (conn.event1Id == event.id ? conn.event2Id : conn.event1Id),
            );

            return Card(
              margin: const EdgeInsets.symmetric(vertical: 4),
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              child: ListTile(
                leading: const Icon(Icons.compare_arrows),
                title: Text(connectedEvent.title),
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(conn.connectionType),
                    Text(conn.description),
                  ],
                ),
                trailing: PopupMenuButton(
                  itemBuilder: (context) => [
                    PopupMenuItem(
                      child: const Text('Edit'),
                      onTap: () => _editConnection(conn),
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

  Future<void> _editConnection(EventConnection connection) async {
    // Implement connection editing dialog
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Edit Connection'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            DropdownButtonFormField<String>(
              value: connection.connectionType,
              decoration: const InputDecoration(labelText: 'Connection Type'),
              items: ['Cause', 'Effect', 'Related']
                  .map((type) => DropdownMenuItem(
                        value: type,
                        child: Text(type),
                      ))
                  .toList(),
              onChanged: (value) {
                // Handle type change
              },
            ),
            TextField(
              decoration: const InputDecoration(labelText: 'Description'),
              controller: TextEditingController(text: connection.description),
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

  // Replace all setState calls with _safeSetState
  void _selectAll() {
    _safeSetState(() {
      selectedEvents = widget.events.map((e) => e.id).toSet();
    });
  }

  void _deselectAll() {
    _safeSetState(() {
      selectedEvents.clear();
      isSelectionMode = false;
    });
  }

  Future<void> _deleteSelected() async {
    final bool confirm = await showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Selected Events'),
        content: Text(
            'Are you sure you want to delete ${selectedEvents.length} events?'),
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
      for (final eventId in selectedEvents.toList()) {
        await widget.onDelete(eventId);
      }
      _safeSetState(() {
        selectedEvents.clear();
        isSelectionMode = false;
      });
    }
  }
}
