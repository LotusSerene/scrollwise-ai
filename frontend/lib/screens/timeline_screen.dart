import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import '../utils/auth.dart';
import '../models/event.dart';
import '../models/location.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/constants.dart';
import 'package:expandable/expandable.dart';
import 'package:intl/intl.dart';
import '../widgets/event_dialog.dart';
import '../widgets/location_dialog.dart';

class TimelineScreen extends StatefulWidget {
  final String projectId;

  const TimelineScreen({Key? key, required this.projectId}) : super(key: key);

  @override
  _TimelineScreenState createState() => _TimelineScreenState();
}

class _TimelineScreenState extends State<TimelineScreen>
    with SingleTickerProviderStateMixin {
  List<Event> events = [];
  List<Location> locations = [];
  bool isLoading = false;
  bool isAlreadyAnalyzed = false;
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadData();
  }

  Future<void> _loadData() async {
    await Future.wait([
      _loadEvents(),
      _loadLocations(),
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
          events = data.map((json) => Event.fromJson(json)).toList();
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
    setState(() => isLoading = true);
    try {
      final headers = await getAuthHeaders();

      // Analyze events
      final eventResponse = await http.post(
        Uri.parse(
            '$apiUrl/events/analyze-chapter?project_id=${widget.projectId}'),
        headers: headers,
      );

      // Analyze locations
      final locationResponse = await http.post(
        Uri.parse(
            '$apiUrl/locations/analyze-chapter?project_id=${widget.projectId}'),
        headers: headers,
      );

      if (eventResponse.statusCode == 200 &&
          locationResponse.statusCode == 200) {
        final eventData = json.decode(eventResponse.body);
        final locationData = json.decode(locationResponse.body);

        setState(() {
          isAlreadyAnalyzed = eventData['alreadyAnalyzed'] == true ||
              locationData['alreadyAnalyzed'] == true;
        });

        await _loadData();
        _showSuccess('Analysis completed successfully');
      } else {
        _showError('Error analyzing chapters');
      }
    } catch (e) {
      _showError('Error analyzing chapters: $e');
    } finally {
      setState(() => isLoading = false);
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
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: const Text('Confirm Delete'),
        content: const Text('Are you sure you want to delete this event?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        final headers = await getAuthHeaders();
        final response = await http.delete(
          Uri.parse('$apiUrl/events/$eventId?project_id=${widget.projectId}'),
          headers: headers,
        );

        if (response.statusCode == 200) {
          await _loadEvents();
          _showSuccess('Event deleted successfully');
        }
      } catch (e) {
        _showError('Error deleting event: $e');
      }
    }
  }

  Future<void> _deleteLocation(String locationId) async {
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
            child: const Text('Delete'),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
          ),
        ],
      ),
    );

    if (confirmed == true) {
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Timeline & Locations'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Events'),
            Tab(text: 'Locations'),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () async {
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
                      Uri.parse(
                          '$apiUrl/events?project_id=${widget.projectId}'),
                      headers: headers,
                      body: json.encode(result),
                    );

                    if (response.statusCode == 200) {
                      await _loadEvents();
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
                      Uri.parse(
                          '$apiUrl/locations?project_id=${widget.projectId}'),
                      headers: headers,
                      body: json.encode(result),
                    );

                    if (response.statusCode == 200) {
                      await _loadLocations();
                      _showSuccess('Location created successfully');
                    }
                  } catch (e) {
                    _showError('Error creating location: $e');
                  }
                }
              }
            },
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _analyzeChapters,
          ),
        ],
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildEventsList(),
                _buildLocationsList(),
              ],
            ),
    );
  }

  Widget _buildEventsList() {
    return ListView.builder(
      itemCount: events.length,
      itemBuilder: (context, index) {
        final event = events[index];
        return Card(
          margin: const EdgeInsets.all(8.0),
          child: ExpandablePanel(
            header: ListTile(
              title: Text(event.title),
              subtitle: Text(DateFormat.yMMMd().format(event.date)),
            ),
            collapsed: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Text(
                event.description,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            expanded: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(event.description),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      IconButton(
                        icon: const Icon(Icons.edit),
                        onPressed: () => _editEvent(event),
                      ),
                      IconButton(
                        icon: const Icon(Icons.delete),
                        onPressed: () => _deleteEvent(event.id),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildLocationsList() {
    return ListView.builder(
      itemCount: locations.length,
      itemBuilder: (context, index) {
        final location = locations[index];
        return Card(
          margin: const EdgeInsets.all(8.0),
          child: ExpandablePanel(
            header: ListTile(
              title: Text(location.name),
            ),
            collapsed: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Text(
                location.description,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            expanded: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(location.description),
                  if (location.coordinates != null) ...[
                    const SizedBox(height: 8),
                    Text('Coordinates: ${location.coordinates}'),
                  ],
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      IconButton(
                        icon: const Icon(Icons.edit),
                        onPressed: () => _editLocation(location),
                      ),
                      IconButton(
                        icon: const Icon(Icons.delete),
                        onPressed: () => _deleteLocation(location.id),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
