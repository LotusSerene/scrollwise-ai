import 'package:flutter/material.dart';
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
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import 'package:flutter_speed_dial/flutter_speed_dial.dart'; // Add this import

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
  late AppState _appState;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _appState = Provider.of<AppState>(context, listen: false);

    // Initialize with saved state if it exists
    final savedState = _appState.getGenerationState('timeline');
    if (savedState != null && savedState.lastGeneratedItem != null) {
      setState(() {
        isAlreadyAnalyzed =
            savedState.lastGeneratedItem['alreadyAnalyzed'] ?? false;
      });
    }
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
    setState(() => isLoading = true); // Add loading state at start
    _appState.setGenerationState('timeline', isGenerating: true);

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

        final analysisResult = {
          'alreadyAnalyzed': eventData['alreadyAnalyzed'] == true ||
              locationData['alreadyAnalyzed'] == true,
          'eventData': eventData,
          'locationData': locationData,
        };

        _appState.setGenerationState(
          'timeline',
          isGenerating: false,
          lastGeneratedItem: analysisResult,
        );

        setState(() {
          isAlreadyAnalyzed = analysisResult['alreadyAnalyzed'];
        });

        await _loadData();
        _showSuccess('Analysis completed successfully');
      } else {
        _showError('Error analyzing chapters');
      }
    } catch (e) {
      _showError('Error analyzing chapters: $e');
    } finally {
      setState(() => isLoading = false); // Add loading state cleanup
      _appState.setGenerationState('timeline', isGenerating: false);
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
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Delete'),
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
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Delete'),
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          _buildHeader(),
          Expanded(
            child: isLoading
                ? const Center(child: CircularProgressIndicator())
                : Column(
                    children: [
                      TabBar(
                        controller: _tabController,
                        tabs: [
                          Tab(
                            icon: const Icon(Icons.event),
                            text: 'Events (${events.length})',
                          ),
                          Tab(
                            icon: const Icon(Icons.place),
                            text: 'Locations (${locations.length})',
                          ),
                        ],
                      ),
                      Expanded(
                        child: TabBarView(
                          controller: _tabController,
                          children: [
                            _buildEventsList(),
                            _buildLocationsList(),
                          ],
                        ),
                      ),
                    ],
                  ),
          ),
        ],
      ),
      floatingActionButton: SpeedDial(
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
              _tabController.animateTo(1); // Switch to locations tab
              _showCreateDialog();
            },
          ),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(16)),
        boxShadow: [
          BoxShadow(
            color: Theme.of(context).shadowColor.withOpacity(0.1),
            blurRadius: 8,
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Timeline & Locations',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  Text(
                    'Track events and important locations',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Theme.of(context)
                              .colorScheme
                              .onSurface
                              .withOpacity(0.6),
                        ),
                  ),
                ],
              ),
              ElevatedButton.icon(
                onPressed: _analyzeChapters,
                icon: const Icon(Icons.auto_awesome),
                label: const Text('Analyze'),
                style: ElevatedButton.styleFrom(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildEventsList() {
    if (events.isEmpty) {
      return _buildEmptyState(
        icon: Icons.calendar_today_outlined,
        message: 'No events found',
        subtitle: 'Add events or analyze chapters to get started',
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: events.length,
      itemBuilder: (context, index) {
        final event = events[index];
        return Card(
          margin: const EdgeInsets.only(bottom: 16),
          child: ExpandablePanel(
            theme: const ExpandableThemeData(
              headerAlignment: ExpandablePanelHeaderAlignment.center,
              hasIcon: true,
            ),
            header: ListTile(
              leading: CircleAvatar(
                backgroundColor: Theme.of(context).colorScheme.primaryContainer,
                child: Icon(
                  Icons.event_available, // Updated icon for events
                  color: Theme.of(context).colorScheme.onPrimaryContainer,
                ),
              ),
              title: Text(
                event.title,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              subtitle: Text(
                DateFormat.yMMMd().format(event.date),
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
            collapsed: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Text(
                event.description,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
            expanded: _buildExpandedEventContent(event),
          ),
        );
      },
    );
  }

  Widget _buildExpandedEventContent(Event event) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Description',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                ),
          ),
          const SizedBox(height: 8),
          Text(event.description),
          if (event.impact != null && event.impact!.isNotEmpty) ...[
            const SizedBox(height: 16),
            Text(
              'Impact',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    color: Theme.of(context).colorScheme.primary,
                  ),
            ),
            const SizedBox(height: 8),
            Text(event.impact!),
          ],
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              TextButton.icon(
                icon: const Icon(Icons.edit),
                label: const Text('Edit'),
                onPressed: () => _editEvent(event),
              ),
              const SizedBox(width: 8),
              TextButton.icon(
                icon: const Icon(Icons.delete),
                label: const Text('Delete'),
                style: TextButton.styleFrom(
                  foregroundColor: Theme.of(context).colorScheme.error,
                ),
                onPressed: () => _deleteEvent(event.id),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildLocationsList() {
    if (locations.isEmpty) {
      return _buildEmptyState(
        icon: Icons.location_on_outlined,
        message: 'No locations found',
        subtitle: 'Add locations or analyze chapters to get started',
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: locations.length,
      itemBuilder: (context, index) {
        final location = locations[index];
        return Card(
          margin: const EdgeInsets.only(bottom: 16),
          child: ExpandablePanel(
            theme: const ExpandableThemeData(
              headerAlignment: ExpandablePanelHeaderAlignment.center,
              hasIcon: true,
            ),
            header: ListTile(
              leading: CircleAvatar(
                backgroundColor:
                    Theme.of(context).colorScheme.secondaryContainer,
                child: Icon(
                  Icons.location_searching,
                  color: Theme.of(context).colorScheme.onSecondaryContainer,
                ),
              ),
              title: Text(
                location.name,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              subtitle: location.coordinates != null
                  ? Text(
                      location.coordinates!,
                      style: Theme.of(context).textTheme.bodySmall,
                    )
                  : null,
            ),
            collapsed: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Text(
                location.description,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
            expanded: _buildExpandedLocationContent(location),
          ),
        );
      },
    );
  }

  Widget _buildExpandedLocationContent(Location location) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Description',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  color: Theme.of(context).colorScheme.secondary,
                ),
          ),
          const SizedBox(height: 8),
          Text(location.description),
          if (location.significance != null &&
              location.significance!.isNotEmpty) ...[
            const SizedBox(height: 16),
            Text(
              'Significance',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    color: Theme.of(context).colorScheme.secondary,
                  ),
            ),
            const SizedBox(height: 8),
            Text(location.significance!),
          ],
          if (location.coordinates != null) ...[
            const SizedBox(height: 16),
            Text(
              'Coordinates',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    color: Theme.of(context).colorScheme.secondary,
                  ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Icon(
                  Icons.map,
                  size: 16,
                  color: Theme.of(context).colorScheme.secondary,
                ),
                const SizedBox(width: 8),
                Text(location.coordinates!),
              ],
            ),
          ],
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              TextButton.icon(
                icon: const Icon(Icons.edit),
                label: const Text('Edit'),
                onPressed: () => _editLocation(location),
              ),
              const SizedBox(width: 8),
              TextButton.icon(
                icon: const Icon(Icons.delete),
                label: const Text('Delete'),
                style: TextButton.styleFrom(
                  foregroundColor: Theme.of(context).colorScheme.error,
                ),
                onPressed: () => _deleteLocation(location.id),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState({
    required IconData icon,
    required String message,
    required String subtitle,
  }) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            icon,
            size: 64,
            color: Theme.of(context).colorScheme.onSurface.withOpacity(0.2),
          ),
          const SizedBox(height: 16),
          Text(
            message,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color:
                      Theme.of(context).colorScheme.onSurface.withOpacity(0.5),
                ),
          ),
          const SizedBox(height: 8),
          Text(
            subtitle,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color:
                      Theme.of(context).colorScheme.onSurface.withOpacity(0.5),
                ),
          ),
        ],
      ),
    );
  }
}
