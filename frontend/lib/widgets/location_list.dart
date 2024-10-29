import 'package:flutter/material.dart';
import '../models/location_connection.dart';
import '../models/location.dart';

class LocationList extends StatefulWidget {
  final List<Location> locations;
  final List<LocationConnection> connections;
  final Function(Location) onEdit;
  final Function(String) onDelete;

  const LocationList({
    Key? key,
    required this.locations,
    required this.connections,
    required this.onEdit,
    required this.onDelete,
  }) : super(key: key);

  @override
  _LocationListState createState() => _LocationListState();
}

class _LocationListState extends State<LocationList> {
  Set<String> selectedLocations = {};
  bool isSelectionMode = false;

  @override
  Widget build(BuildContext context) {
    if (widget.locations.isEmpty) {
      return Card(
        child: Container(
          padding: const EdgeInsets.all(24),
          alignment: Alignment.center,
          child: Column(
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

    return Column(
      children: [
        if (isSelectionMode) _buildSelectionControls(),
        ListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: widget.locations.length,
          itemBuilder: (context, index) {
            final location = widget.locations[index];
            return _buildLocationCard(location);
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
          setState(() {
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
                      setState(() {
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
                Text(
                  connectedLocation.name,
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
            if (conn.travelRoute != null) ...[
              const SizedBox(height: 8),
              Text(
                'Travel Route: ${conn.travelRoute}',
                style: TextStyle(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
            if (conn.culturalExchange != null) ...[
              const SizedBox(height: 4),
              Text(
                'Cultural Exchange: ${conn.culturalExchange}',
                style: TextStyle(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _selectAll() {
    setState(() {
      selectedLocations = widget.locations.map((e) => e.id).toSet();
    });
  }

  void _deselectAll() {
    setState(() {
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
      for (final locationId in selectedLocations.toList()) {
        await widget.onDelete(locationId);
      }
      setState(() {
        selectedLocations.clear();
        isSelectionMode = false;
      });
    }
  }
}
