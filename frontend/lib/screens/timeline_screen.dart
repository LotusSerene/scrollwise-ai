import 'package:flutter/material.dart';
import '../utils/auth.dart';
import '../models/event.dart';
import '../models/location.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/constants.dart';
import '../widgets/event_dialog.dart';
import '../widgets/location_dialog.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import 'package:flutter_speed_dial/flutter_speed_dial.dart'; // Add this import
import '../models/event_connection.dart';
import '../models/location_connection.dart';
import '../widgets/event_list.dart';
import '../widgets/location_list.dart';

class TimelineScreen extends StatefulWidget {
  final String projectId;

  const TimelineScreen({Key? key, required this.projectId}) : super(key: key);

  @override
  State<TimelineScreen> createState() => _TimelineScreenState();
}

class _TimelineScreenState extends State<TimelineScreen>
    with SingleTickerProviderStateMixin {
  List<Event> events = [];
  List<Location> locations = [];
  bool isLoading = false;
  late TabController _tabController;
  List<EventConnection> eventConnections = [];
  List<LocationConnection> locationConnections = [];
  bool isSelectionMode = false;
  List<String> selectedEvents = [];
  List<String> selectedLocations = [];

  @override
  void initState() {
    super.initState();
    final appState = Provider.of<AppState>(context, listen: false);

    // Update tab controller to handle 4 tabs instead of 2
    _tabController = TabController(
      length: 4,
      vsync: this,
      initialIndex: appState.timelineState['activeTab'] ?? 0,
    );

    // Add listener to save tab state
    _tabController.addListener(() {
      appState.updateTimelineProgress(activeTab: _tabController.index);
    });

    _loadData();
  }

  Future<void> _loadData() async {
    await Future.wait([
      _loadEvents(),
      _loadLocations(),
      _loadEventConnections(),
      _loadLocationConnections(),
    ]);
  }

  Future<void> _loadEvents() async {
    setState(() => isLoading = true);
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/events?project_id=${widget.projectId}'),
        headers: headers,
      );
      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body)['events'];
        setState(() {
          events = data.map((json) => Event.fromJson(json)).toList()
            ..sort((a, b) => a.date.compareTo(b.date)); // Sort by date
        });
      }
    } catch (e) {
      _showError('Error loading events: $e');
    } finally {
      setState(() => isLoading = false);
    }
  }

  Future<void> _loadLocations() async {
    setState(() => isLoading = true);
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/locations?project_id=${widget.projectId}'),
        headers: headers,
      );
      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body)['locations'];
        setState(() {
          locations = data.map((json) => Location.fromJson(json)).toList();
        });
      }
    } catch (e) {
      _showError('Error loading locations: $e');
    } finally {
      setState(() => isLoading = false);
    }
  }

  Future<void> _analyzeChapters() async {
    final appState = Provider.of<AppState>(context, listen: false);
    setState(() => isLoading = true);
    appState.updateTimelineProgress(isGenerating: true);

    try {
      final headers = await getAuthHeaders();

      // Removed chapter_id parameter since it's handled server-side
      final eventResponse = await http.post(
        Uri.parse(
            '$apiUrl/events/analyze-chapter?project_id=${widget.projectId}'),
        headers: headers,
      );

      final locationResponse = await http.post(
        Uri.parse(
            '$apiUrl/locations/analyze-chapter?project_id=${widget.projectId}'),
        headers: headers,
      );

      if (eventResponse.statusCode == 200 &&
          locationResponse.statusCode == 200) {
        final eventData = json.decode(eventResponse.body);
        final locationData = json.decode(locationResponse.body);

        final analysisResult = {
          'alreadyAnalyzed': eventData['alreadyAnalyzed'] == true ||
              locationData['alreadyAnalyzed'] == true,
          'eventData': eventData,
          'locationData': locationData,
        };

        appState.updateTimelineProgress(
          isGenerating: false,
          lastGeneratedItem: analysisResult,
          isAlreadyAnalyzed: analysisResult['alreadyAnalyzed'],
        );

        await _loadData();
        _showSuccess('Analysis completed successfully');
      } else {
        _showError('Error analyzing chapters');
      }
    } catch (e) {
      _showError('Error analyzing chapters: $e');
    } finally {
      setState(() => isLoading = false);
      appState.updateTimelineProgress(isGenerating: false);
    }
  }

  Future<void> _editEvent(Event event) async {
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (BuildContext context) => EventDialog(event: event),
    );

    if (result != null) {
      try {
        final headers = await getAuthHeaders();
        headers['Content-Type'] = 'application/json';

        final response = await http.put(
          Uri.parse(
              '$apiUrl/events/${event.id}?project_id=${widget.projectId}'),
          headers: headers,
          body: json.encode(result),
        );

        if (response.statusCode == 200) {
          await _loadEvents();
          _showSuccess('Event updated successfully');
        }
      } catch (e) {
        _showError('Error updating event: $e');
      }
    }
  }

  Future<void> _editLocation(Location location) async {
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (BuildContext context) => LocationDialog(location: location),
    );

    if (result != null) {
      try {
        final headers = await getAuthHeaders();
        headers['Content-Type'] = 'application/json';

        final response = await http.put(
          Uri.parse(
              '$apiUrl/locations/${location.id}?project_id=${widget.projectId}'),
          headers: headers,
          body: json.encode(result),
        );

        if (response.statusCode == 200) {
          await _loadLocations();
          _showSuccess('Location updated successfully');
        }
      } catch (e) {
        _showError('Error updating location: $e');
      }
    }
  }

  Future<void> _deleteEvent(String eventId) async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.delete(
        Uri.parse('$apiUrl/events/$eventId?project_id=${widget.projectId}'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        setState(() {
          events.removeWhere((event) => event.id == eventId);
        });
      } else {
        throw Exception('Failed to delete event');
      }
    } catch (e) {
      _showError('Error deleting event: $e');
    }
  }

  Future<void> _deleteLocation(String locationId,
      {bool skipConfirmation = false}) async {
    // Skip confirmation dialog if skipConfirmation is true (for batch deletions)
    if (!skipConfirmation) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (BuildContext context) => AlertDialog(
          title: const Text('Confirm Delete'),
          content: const Text('Are you sure you want to delete this location?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context, true),
              style: TextButton.styleFrom(foregroundColor: Colors.red),
              child: const Text('Delete'),
            ),
          ],
        ),
      );

      if (confirmed != true) return;
    }

    try {
      final headers = await getAuthHeaders();
      final response = await http.delete(
        Uri.parse(
            '$apiUrl/locations/$locationId?project_id=${widget.projectId}'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        await _loadLocations();
        _showSuccess('Location deleted successfully');
      }
    } catch (e) {
      _showError('Error deleting location: $e');
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.red),
    );
  }

  void _showSuccess(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.green),
    );
  }

  Future<void> _showCreateDialog() async {
    if (_tabController.index == 0) {
      final result = await showDialog<Map<String, dynamic>>(
        context: context,
        builder: (BuildContext context) => const EventDialog(),
      );
      if (result != null) {
        try {
          final headers = await getAuthHeaders();
          headers['Content-Type'] = 'application/json';
          final response = await http.post(
            Uri.parse('$apiUrl/events?project_id=${widget.projectId}'),
            headers: headers,
            body: json.encode(result),
          );
          if (response.statusCode == 201) {
            await _loadEvents(); // This will refresh the events list
            _showSuccess('Event created successfully');
          }
        } catch (e) {
          _showError('Error creating event: $e');
        }
      }
    } else {
      final result = await showDialog<Map<String, dynamic>>(
        context: context,
        builder: (BuildContext context) => const LocationDialog(),
      );
      if (result != null) {
        try {
          final headers = await getAuthHeaders();
          headers['Content-Type'] = 'application/json';
          final response = await http.post(
            Uri.parse('$apiUrl/locations?project_id=${widget.projectId}'),
            headers: headers,
            body: json.encode(result),
          );
          if (response.statusCode == 201) {
            await _loadLocations(); // This will refresh the locations list
            _showSuccess('Location created successfully');
          }
        } catch (e) {
          _showError('Error creating location: $e');
        }
      }
    }
  }

  Future<void> _loadEventConnections() async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/events/connections?project_id=${widget.projectId}'),
        headers: headers,
      );
      if (response.statusCode == 200) {
        final List<dynamic> data =
            json.decode(response.body)['event_connections'];
        setState(() {
          eventConnections =
              data.map((json) => EventConnection.fromJson(json)).toList();
        });
      }
    } catch (e) {
      _showError('Error loading event connections: $e');
    }
  }

  Future<void> _deleteEventConnection(String connectionId) async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.delete(
        Uri.parse(
            '$apiUrl/events/connections/$connectionId?project_id=${widget.projectId}'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        await _loadEventConnections();
        _showSuccess('Connection deleted successfully');
      }
    } catch (e) {
      _showError('Error deleting connection: $e');
    }
  }

  Future<void> _loadLocationConnections() async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse(
            '$apiUrl/locations/connections?project_id=${widget.projectId}'),
        headers: headers,
      );
      if (response.statusCode == 200) {
        final List<dynamic> data =
            json.decode(response.body)['location_connections'];
        setState(() {
          locationConnections =
              data.map((json) => LocationConnection.fromJson(json)).toList();
        });
      }
    } catch (e) {
      _showError('Error loading location connections: $e');
    }
  }

  Future<void> _deleteLocationConnection(String connectionId) async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.delete(
        Uri.parse(
            '$apiUrl/locations/connections/$connectionId?project_id=${widget.projectId}'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        await _loadLocationConnections();
        _showSuccess('Connection deleted successfully');
      }
    } catch (e) {
      _showError('Error deleting connection: $e');
    }
  }

  Future<void> _updateEventConnection(EventConnection connection) async {
    try {
      final headers = await getAuthHeaders();
      headers['Content-Type'] = 'application/json';

      final response = await http.put(
        Uri.parse(
            '$apiUrl/events/connections/${connection.id}?project_id=${widget.projectId}'),
        headers: headers,
        body: json.encode({
          'connection_type': connection.connectionType,
          'description': connection.description,
          'impact': '', // Add impact if needed
        }),
      );

      if (response.statusCode == 200) {
        await _loadEventConnections();
        _showSuccess('Connection updated successfully');
      }
    } catch (e) {
      _showError('Error updating connection: $e');
    }
  }

  Future<void> _updateLocationConnection(LocationConnection connection) async {
    try {
      final headers = await getAuthHeaders();
      headers['Content-Type'] = 'application/json';

      final response = await http.put(
        Uri.parse(
            '$apiUrl/locations/connections/${connection.id}?project_id=${widget.projectId}'),
        headers: headers,
        body: json.encode({
          'travel_route': connection.travelRoute,
          'cultural_exchange': connection.culturalExchange,
        }),
      );

      if (response.statusCode == 200) {
        await _loadLocationConnections();
        _showSuccess('Connection updated successfully');
      }
    } catch (e) {
      _showError('Error updating connection: $e');
    }
  }

  Future<void> _analyzeConnections() async {
    setState(() => isLoading = true);
    try {
      final headers = await getAuthHeaders();

      // Analyze event connections
      final eventResponse = await http.post(
        Uri.parse(
            '$apiUrl/events/analyze-connections?project_id=${widget.projectId}'),
        headers: headers,
      );

      // Analyze location connections
      final locationResponse = await http.post(
        Uri.parse(
            '$apiUrl/locations/analyze-connections?project_id=${widget.projectId}'),
        headers: headers,
      );

      final eventData = json.decode(eventResponse.body);
      final locationData = json.decode(locationResponse.body);

      // Handle events separately
      if (eventData['skip'] == true) {
        _showInfo('Not enough events to analyze connections');
      } else if (eventData['connections'] != null) {
        await _loadEventConnections();
        _showSuccess('Event connections analyzed');
      }

      // Handle locations separately
      if (locationData['skip'] == true) {
        _showInfo('Not enough locations to analyze connections');
      } else if (locationData['connections'] != null) {
        await _loadLocationConnections();
        _showSuccess('Location connections analyzed');
      }

      // Combined message if both are skipped
      if (eventData['skip'] == true && locationData['skip'] == true) {
        _showInfo(
            'Need at least 2 events and 2 locations to analyze connections');
      }
    } catch (e) {
      _showError('Error analyzing connections: $e');
    } finally {
      setState(() => isLoading = false);
    }
  }

  void _showInfo(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Theme.of(context).colorScheme.secondary,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          TabBar(
            controller: _tabController,
            tabs: const [
              Tab(text: 'Events'),
              Tab(text: 'Locations'),
              Tab(text: 'Event Connections'),
              Tab(text: 'Location Connections'),
            ],
          ),
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                _buildEventsView(),
                _buildLocationsView(),
                _buildEventConnectionsView(),
                _buildLocationConnectionsView(),
              ],
            ),
          ),
        ],
      ),
      floatingActionButton: _buildSpeedDial(),
    );
  }

  Widget _buildEventsView() {
    if (isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSectionHeader('Timeline', Icons.timeline),
          Expanded(
            child: EventList(
              events: events,
              connections: eventConnections,
              onEdit: _editEvent,
              onDelete: _deleteEvent,
              onDeleteConnection: _deleteEventConnection,
              onUpdateConnection: _updateEventConnection,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLocationsView() {
    if (isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSectionHeader('Locations', Icons.place),
          LocationList(
            locations: locations,
            connections: locationConnections,
            onEdit: _editLocation,
            onDelete: (id) => _deleteLocation(id, skipConfirmation: false),
            onBatchDelete: _batchDeleteLocations,
            onDeleteConnection: _deleteLocationConnection,
            onUpdateConnection: _updateLocationConnection,
          ),
        ],
      ),
    );
  }

  Widget _buildEventConnectionsView() {
    if (isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSectionHeader('Event Connections', Icons.compare_arrows),
          _buildConnectionsGrid(events, eventConnections),
        ],
      ),
    );
  }

  Widget _buildLocationConnectionsView() {
    if (isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSectionHeader('Location Connections', Icons.compare_arrows),
          _buildLocationConnectionsGrid(locations, locationConnections),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title, IconData icon) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Row(
        children: [
          Icon(icon, color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: 8),
          Text(
            title,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildSpeedDial() {
    if (isSelectionMode) return const SizedBox.shrink();
    return SpeedDial(
      icon: Icons.add,
      activeIcon: Icons.close,
      backgroundColor: Theme.of(context).colorScheme.primary,
      foregroundColor: Theme.of(context).colorScheme.onPrimary,
      children: [
        SpeedDialChild(
          child: const Icon(Icons.event),
          label: 'Add Event',
          onTap: () => _showCreateDialog(),
        ),
        SpeedDialChild(
          child: const Icon(Icons.place),
          label: 'Add Location',
          onTap: () {
            _tabController.animateTo(1);
            _showCreateDialog();
          },
        ),
        SpeedDialChild(
          child: const Icon(Icons.auto_awesome),
          label: 'Analyze New Events/Locations',
          onTap: () => _analyzeChapters(),
        ),
        SpeedDialChild(
          child: const Icon(Icons.compare_arrows),
          label: 'Analyze Connections',
          onTap: () => _analyzeConnections(),
        ),
      ],
    );
  }

  Widget _buildConnectionsGrid(
      List<Event> events, List<EventConnection> connections) {
    if (connections.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Icon(
                Icons.compare_arrows,
                size: 48,
                color: Theme.of(context).colorScheme.secondary.withOpacity(0.5),
              ),
              const SizedBox(height: 16),
              Text(
                'No event connections found',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              Text(
                'Use the analyze button to discover connections',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context)
                          .colorScheme
                          .onSurface
                          .withOpacity(0.7),
                    ),
              ),
            ],
          ),
        ),
      );
    }

    // Filter out connections where either event doesn't exist
    final validConnections = connections.where((connection) {
      try {
        events.firstWhere((e) => e.id == connection.event1Id);
        events.firstWhere((e) => e.id == connection.event2Id);
        return true;
      } catch (e) {
        return false;
      }
    }).toList();

    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        childAspectRatio: 1.5,
        crossAxisSpacing: 16,
        mainAxisSpacing: 16,
      ),
      itemCount: validConnections.length,
      itemBuilder: (context, index) {
        final connection = validConnections[index];
        final event1 = events.firstWhere((e) => e.id == connection.event1Id);
        final event2 = events.firstWhere((e) => e.id == connection.event2Id);

        return Card(
          elevation: 2,
          child: InkWell(
            onTap: () => _showConnectionActions(event1, event2),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          '${event1.title} → ${event2.title}',
                          style: Theme.of(context).textTheme.titleSmall,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                  const Spacer(),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.secondaryContainer,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      connection.connectionType,
                      style: TextStyle(
                        color:
                            Theme.of(context).colorScheme.onSecondaryContainer,
                        fontSize: 12,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    connection.description,
                    style: Theme.of(context).textTheme.bodySmall,
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildLocationConnectionsGrid(
      List<Location> locations, List<LocationConnection> connections) {
    if (connections.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Icon(
                Icons.compare_arrows,
                size: 48,
                color: Theme.of(context).colorScheme.secondary.withOpacity(0.5),
              ),
              const SizedBox(height: 16),
              Text(
                'No location connections found',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              Text(
                'Use the analyze button to discover connections',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context)
                          .colorScheme
                          .onSurface
                          .withOpacity(0.7),
                    ),
              ),
            ],
          ),
        ),
      );
    }

    // Filter out connections where either location doesn't exist
    final validConnections = connections.where((connection) {
      try {
        locations.firstWhere((l) => l.id == connection.location1Id);
        locations.firstWhere((l) => l.id == connection.location2Id);
        return true;
      } catch (e) {
        return false;
      }
    }).toList();

    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        childAspectRatio: 1.5,
        crossAxisSpacing: 16,
        mainAxisSpacing: 16,
      ),
      itemCount: validConnections.length,
      itemBuilder: (context, index) {
        final connection = validConnections[index];
        final location1 =
            locations.firstWhere((l) => l.id == connection.location1Id);
        final location2 =
            locations.firstWhere((l) => l.id == connection.location2Id);

        return Card(
          elevation: 2,
          child: InkWell(
            onTap: () => _showLocationConnectionActions(location1, location2),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          '${location1.name} ↔ ${location2.name}',
                          style: Theme.of(context).textTheme.titleSmall,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                  const Spacer(),
                  ...[
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.secondaryContainer,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        'Travel Route',
                        style: TextStyle(
                          color: Theme.of(context)
                              .colorScheme
                              .onSecondaryContainer,
                          fontSize: 12,
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      connection.travelRoute,
                      style: Theme.of(context).textTheme.bodySmall,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                  ...[
                    const SizedBox(height: 8),
                    Text(
                      connection.culturalExchange,
                      style: Theme.of(context).textTheme.bodySmall,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  void _showConnectionActions(Event event1, Event event2) {
    showModalBottomSheet(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.edit),
              title: Text('Edit ${event1.title}'),
              onTap: () {
                Navigator.pop(context);
                _editEvent(event1);
              },
            ),
            ListTile(
              leading: const Icon(Icons.edit),
              title: Text('Edit ${event2.title}'),
              onTap: () {
                Navigator.pop(context);
                _editEvent(event2);
              },
            ),
            ListTile(
              leading: const Icon(Icons.delete),
              title: Text('Delete ${event1.title}'),
              textColor: Colors.red,
              iconColor: Colors.red,
              onTap: () {
                Navigator.pop(context);
                _deleteEvent(event1.id);
              },
            ),
            ListTile(
              leading: const Icon(Icons.delete),
              title: Text('Delete ${event2.title}'),
              textColor: Colors.red,
              iconColor: Colors.red,
              onTap: () {
                Navigator.pop(context);
                _deleteEvent(event2.id);
              },
            ),
          ],
        ),
      ),
    );
  }

  void _showLocationConnectionActions(Location location1, Location location2) {
    showModalBottomSheet(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.edit),
              title: Text('Edit ${location1.name}'),
              onTap: () {
                Navigator.pop(context);
                _editLocation(location1);
              },
            ),
            ListTile(
              leading: const Icon(Icons.edit),
              title: Text('Edit ${location2.name}'),
              onTap: () {
                Navigator.pop(context);
                _editLocation(location2);
              },
            ),
            ListTile(
              leading: const Icon(Icons.delete),
              title: Text('Delete ${location1.name}'),
              textColor: Colors.red,
              iconColor: Colors.red,
              onTap: () {
                Navigator.pop(context);
                _deleteLocation(location1.id);
              },
            ),
            ListTile(
              leading: const Icon(Icons.delete),
              title: Text('Delete ${location2.name}'),
              textColor: Colors.red,
              iconColor: Colors.red,
              onTap: () {
                Navigator.pop(context);
                _deleteLocation(location2.id);
              },
            ),
          ],
        ),
      ),
    );
  }

  // Add this method for batch deletions
  Future<void> _batchDeleteLocations(List<String> locationIds) async {
    try {
      final headers = await getAuthHeaders();

      // Delete all locations without individual confirmations
      for (final locationId in locationIds) {
        final response = await http.delete(
          Uri.parse(
              '$apiUrl/locations/$locationId?project_id=${widget.projectId}'),
          headers: headers,
        );

        if (response.statusCode != 200) {
          throw Exception('Failed to delete location $locationId');
        }
      }

      await _loadLocations();
      _showSuccess('Selected locations deleted successfully');
    } catch (e) {
      _showError('Error deleting locations: $e');
    }
  }
}
