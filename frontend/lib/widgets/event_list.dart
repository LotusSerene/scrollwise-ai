import 'package:flutter/material.dart';
import '../models/event_connection.dart';
import '../models/event.dart';

class EventList extends StatefulWidget {
  final List<Event> events;
  final List<EventConnection> connections;
  final Function(Event) onEdit;
  final Function(String) onDelete;

  const EventList({
    Key? key,
    required this.events,
    required this.connections,
    required this.onEdit,
    required this.onDelete,
  }) : super(key: key);

  @override
  _EventListState createState() => _EventListState();
}

class _EventListState extends State<EventList> {
  Set<String> selectedEvents = {};
  bool isSelectionMode = false;

  @override
  Widget build(BuildContext context) {
    if (widget.events.isEmpty) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(16.0),
          child: Text('No events created yet'),
        ),
      );
    }

    return Column(
      children: [
        if (isSelectionMode) _buildSelectionControls(),
        ListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: widget.events.length,
          itemBuilder: (context, index) {
            final event = widget.events[index];
            return _buildEventCard(event);
          },
        ),
      ],
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
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _selectAll() {
    setState(() {
      selectedEvents = widget.events.map((e) => e.id).toSet();
    });
  }

  void _deselectAll() {
    setState(() {
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
      setState(() {
        selectedEvents.clear();
        isSelectionMode = false;
      });
    }
  }
}
