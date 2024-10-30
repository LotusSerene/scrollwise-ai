import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import 'dart:io';
import 'dart:async';
import 'universe_screen.dart';
import 'package:flutter_speed_dial/flutter_speed_dial.dart';
import 'collaboration_screen.dart';

final GlobalKey<TextFieldState> _tokenFieldKey = GlobalKey<TextFieldState>();

final GlobalKey<TextFieldState> _tokenFieldKey = GlobalKey<TextFieldState>();

class ProjectsScreen extends StatefulWidget {
  const ProjectsScreen({Key? key}) : super(key: key);

  @override
  State<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends State<ProjectsScreen>
    with SingleTickerProviderStateMixin {
  bool _mounted = true;
  bool _isLoading = true;
  bool _isLoadingMore = false;
  List<dynamic> _projects = [];
  List<dynamic> _collaborations = [];
  List<dynamic> _displayedProjects = [];
  final List<dynamic> _universes = [];
  final List<dynamic> _displayedUniverses = [];
  final ScrollController _projectsScrollController = ScrollController();
  final ScrollController _universesScrollController = ScrollController();
  final int _itemsPerPage = 10;
  final _projectFormKey = GlobalKey<FormState>();
  final _universeFormKey = GlobalKey<FormState>();
  final _projectNameController = TextEditingController();
  final _projectDescriptionController = TextEditingController();
  final _universeNameController = TextEditingController();
  String? _selectedUniverseId;
  // Add TabController
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    // Initialize TabController
    _tabController = TabController(length: 3, vsync: this);
    _projectsScrollController.addListener(_onProjectsScroll);
    _universesScrollController.addListener(_onUniversesScroll);
    _fetchData();
  }

  @override
  void dispose() {
    // Dispose TabController
    _tabController.dispose();
    _mounted = false;
    _projectNameController.dispose();
    _projectDescriptionController.dispose();
    _universeNameController.dispose();
    _projectsScrollController.dispose();
    _universesScrollController.dispose();
    super.dispose();
  }

  void _safeSetState(VoidCallback fn) {
    if (_mounted && mounted) {
      setState(fn);
    }
  }

  void _onProjectsScroll() {
    if (_projectsScrollController.position.pixels >=
        _projectsScrollController.position.maxScrollExtent * 0.8) {
      _loadMoreProjects();
    }
  }

  void _onUniversesScroll() {
    if (_universesScrollController.position.pixels >=
        _universesScrollController.position.maxScrollExtent * 0.8) {
      _loadMoreUniverses();
    }
  }

  void _loadMoreProjects() {
    if (_isLoadingMore) return;

    final startIndex = _displayedProjects.length;
    if (startIndex >= _projects.length) return;

    _safeSetState(() {
      _isLoadingMore = true;
    });

    Future.delayed(const Duration(milliseconds: 500), () {
      if (!_mounted) return;

      final newItems = _projects.skip(startIndex).take(_itemsPerPage).toList();

      _safeSetState(() {
        _displayedProjects.addAll(newItems);
        _isLoadingMore = false;
      });
    });
  }

  void _loadMoreUniverses() {
    if (_isLoadingMore) return;

    final startIndex = _displayedUniverses.length;
    if (startIndex >= _universes.length) return;

    _safeSetState(() {
      _isLoadingMore = true;
    });

    Future.delayed(const Duration(milliseconds: 500), () {
      if (!_mounted) return;

      final newItems = _universes.skip(startIndex).take(_itemsPerPage).toList();

      _safeSetState(() {
        _displayedUniverses.addAll(newItems);
        _isLoadingMore = false;
      });
    });
  }

  Future<void> _fetchData() async {
    if (!_mounted) return;
    setState(() {
      _isLoading = true;
    });
    try {
      await Future.wait([
        _fetchProjects(),
        _fetchUniverses(),
        _fetchCollaborations(),
      ]);
    } catch (error) {
      print('Error fetching data: $error');
      if (!_mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error fetching data: ${error.toString()}'),
          behavior: SnackBarBehavior.fixed, // Use fixed instead of floating
        ),
      );
    } finally {
      if (_mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _fetchProjects() async {
    if (!_mounted) return;

    try {
      final headers = await getAuthHeaders();
      final response = await http
          .get(
            Uri.parse('$apiUrl/projects'),
            headers: headers,
          )
          .timeout(const Duration(seconds: 10));

      if (!_mounted) return;

      if (response.statusCode == 200) {
        final projects =
            json.decode(utf8.decode(response.bodyBytes))['projects'];
        _safeSetState(() {
          _projects = projects;
          _displayedProjects = projects.take(_itemsPerPage).toList();
        });
      } else {
        throw Exception('Failed to load projects');
      }
    } catch (error) {
      if (!_mounted) return;
      rethrow;
    }
  }

  Future<List<dynamic>> _fetchUniverses() async {
    if (!_mounted) return [];
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/universes'),
        headers: await getAuthHeaders(),
      );
      if (!_mounted) return [];
      if (response.statusCode == 200) {
        return json.decode(utf8.decode(response.bodyBytes));
      } else {
        throw Exception('Failed to load universes: ${response.statusCode}');
      }
    } catch (error) {
      print('Error fetching universes: $error');
      rethrow;
    }
  }

  Future<void> _fetchCollaborations() async {
    if (!_mounted) return;
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/collaborations'),
        headers: await getAuthHeaders(),
      );

      if (response.statusCode == 200) {
        if (!_mounted) return;
        setState(() {
          _collaborations =
              json.decode(utf8.decode(response.bodyBytes))['collaborations'];
        });
      }
    } catch (error) {
      print('Error fetching collaborations: $error');
      rethrow;
    }
  }

  Future<void> _createProject() async {
    if (_projectFormKey.currentState!.validate()) {
      try {
        final headers = {
          ...await getAuthHeaders(),
          'Content-Type': 'application/json',
        };

        final requestBody = {
          'name': _projectNameController.text,
          'description': _projectDescriptionController.text,
          'universe_id':
              _selectedUniverseId == 'no_universe' ? null : _selectedUniverseId,
        };

        final response = await http.post(
          Uri.parse('$apiUrl/projects'),
          headers: headers,
          body: utf8.encode(json.encode(requestBody)),
        );

        if (response.statusCode == 201 || response.statusCode == 200) {
          // Clear the form
          _projectNameController.clear();
          _projectDescriptionController.clear();
          _selectedUniverseId = 'no_universe';

          // Refresh the projects list
          await _fetchProjects();

          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Project created successfully'),
                behavior: SnackBarBehavior.fixed,
              ),
            );
          }
        } else {
          final errorData = json.decode(utf8.decode(response.bodyBytes));
          throw Exception(errorData['detail'] ?? 'Unknown error occurred');
        }
      } catch (error) {
        print('Error creating project: $error');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Error creating project: ${error.toString()}'),
              behavior: SnackBarBehavior.fixed,
            ),
          );
        }
      }
    }
  }

  Future<void> _createUniverse(String name) async {
    try {
      final response = await http.post(
        Uri.parse('$apiUrl/universes'),
        headers: {
          ...await getAuthHeaders(),
          'Content-Type': 'application/json', // Add content type header
        },
        body: utf8
            .encode(json.encode({'name': name})), // Properly encode the body
      );

      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Universe created successfully'),
            behavior: SnackBarBehavior.fixed,
          ),
        );
        _fetchData();
      } else {
        throw Exception('Failed to create universe');
      }
    } catch (error) {
      print('Error creating universe: $error');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error creating universe: ${error.toString()}'),
          behavior: SnackBarBehavior.fixed,
        ),
      );
    }
  }

  Future<void> _updateUniverse(String universeId, String newName) async {
    try {
      final response = await http.put(
        Uri.parse('$apiUrl/universes/$universeId'),
        headers: await getAuthHeaders(),
        body: json.encode({'name': newName}),
      );

      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Universe updated successfully'),
            behavior: SnackBarBehavior.fixed, // Use fixed instead of floating
          ),
        );
        _fetchData();
      } else {
        throw Exception('Failed to update universe');
      }
    } catch (error) {
      print('Error updating universe: $error');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error updating universe: ${error.toString()}'),
          behavior: SnackBarBehavior.fixed, // Use fixed instead of floating
        ),
      );
    }
  }

  Future<void> _deleteUniverse(String universeId) async {
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/universes/$universeId'),
        headers: await getAuthHeaders(),
      );

      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Universe deleted successfully'),
            behavior: SnackBarBehavior.fixed, // Use fixed instead of floating
          ),
        );
        _fetchData();
      } else {
        throw Exception('Failed to delete universe');
      }
    } catch (error) {
      print('Error deleting universe: $error');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error deleting universe: ${error.toString()}'),
          behavior: SnackBarBehavior.fixed, // Use fixed instead of floating
        ),
      );
    }
  }

  void _showUniverseDialog({String? universeId, String? universeName}) {
    final TextEditingController controller =
        TextEditingController(text: universeName);
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title:
              Text(universeId == null ? 'Create Universe' : 'Update Universe'),
          content: Form(
            key: _universeFormKey,
            child: TextFormField(
              controller: controller,
              decoration: const InputDecoration(labelText: 'Universe Name'),
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please enter a universe name';
                }
                return null;
              },
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
              child: Text(universeId == null ? 'Create' : 'Update'),
              onPressed: () {
                if (_universeFormKey.currentState!.validate()) {
                  if (universeId == null) {
                    _createUniverse(controller.text);
                  } else {
                    _updateUniverse(universeId, controller.text);
                  }
                  Navigator.of(context).pop();
                }
              },
            ),
          ],
        );
      },
    );
  }

  // Add this method to update a project's universe
  Future<void> _updateProjectUniverse(
      String projectId, String? universeId) async {
    try {
      final response = await http.put(
        Uri.parse('$apiUrl/projects/$projectId/universe'),
        headers: {
          ...await getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: json.encode(
            {'universe_id': universeId == 'no_universe' ? null : universeId}),
      );

      if (response.statusCode == 200) {
        await _fetchProjects(); // Refresh the projects list
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Project updated successfully'),
              behavior: SnackBarBehavior.fixed,
            ),
          );
        }
      } else {
        throw Exception('Failed to update project');
      }
    } catch (error) {
      print('Error updating project universe: $error');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error updating project: ${error.toString()}'),
            behavior: SnackBarBehavior.fixed,
          ),
        );
      }
    }
  }

  // Add these new methods for universe management
  Widget _buildUniversesTab() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_universes.isEmpty) {
      return _buildEmptyUniversesState();
    }

    return GridView.builder(
      controller: _universesScrollController,
      padding: const EdgeInsets.all(16),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        childAspectRatio: 1.3,
        crossAxisSpacing: 16,
        mainAxisSpacing: 16,
      ),
      itemCount: _displayedUniverses.length + (_isLoadingMore ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _displayedUniverses.length) {
          return _buildLoadingIndicator();
        }
        return _buildUniverseCard(_displayedUniverses[index]);
      },
    );
  }

  Widget _buildLoadingIndicator() {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16),
      alignment: Alignment.center,
      child: const CircularProgressIndicator(),
    );
  }

  Widget _buildUniverseCard(Map<String, dynamic> universe) {
    final universeId = universe['id']?.toString();
    if (universeId == null) {
      return const SizedBox(); // Skip rendering invalid universes
    }

    return Card(
      elevation: 4,
      child: InkWell(
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => UniverseScreen(universeId: universe['id']),
            ),
          );
        },
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.public,
                      color: Theme.of(context).colorScheme.primary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      universe['name'],
                      style: Theme.of(context).textTheme.titleMedium,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  PopupMenuButton(
                    itemBuilder: (context) => [
                      PopupMenuItem(
                        child: const Text('Edit'),
                        onTap: () => _showUniverseDialog(
                          universeId: universe['id'],
                          universeName: universe['name'],
                        ),
                      ),
                      PopupMenuItem(
                        child: const Text('Delete'),
                        onTap: () => _deleteUniverse(universe['id']),
                      ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Expanded(
                child: Text(
                  universe['description'] ?? 'No description',
                  style: Theme.of(context).textTheme.bodyMedium,
                  overflow: TextOverflow.ellipsis,
                  maxLines: 3,
                ),
              ),
              const Spacer(),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Projects: ${universe['project_count'] ?? 0}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  Text(
                    'Entries: ${universe['entry_count'] ?? 0}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        drawer: _buildDrawer(), // Add the drawer here
        appBar: AppBar(
          title: const Text('Your Projects'),
          bottom: TabBar(
            controller: _tabController,
            tabs: [
              Tab(
                icon: const Icon(Icons.folder_special),
                text: 'Projects (${_projects.length})',
              ),
              const Tab(
                icon: Icon(Icons.public),
                text: 'Universes',
              ),
              Tab(
                icon: const Icon(Icons.people),
                text: 'Collaborations (${_collaborations.length})',
              ),
            ],
          ),
        ),
        floatingActionButton: _buildFloatingActionButton(),
        body: TabBarView(
          controller: _tabController,
          children: [
            _buildProjectsTab(),
            _buildUniversesTab(),
            _buildCollaborationsTab(),
          ],
        ),
      ),
    );
  }

  Widget _buildProjectsTab() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_projects.isEmpty) {
      return _buildEmptyProjectsState();
    }

    return GridView.builder(
      controller: _projectsScrollController,
      padding: const EdgeInsets.all(16),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        childAspectRatio: 1.3,
        crossAxisSpacing: 16,
        mainAxisSpacing: 16,
      ),
      itemCount: _displayedProjects.length + (_isLoadingMore ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _displayedProjects.length) {
          return _buildLoadingIndicator();
        }
        return _buildProjectCard(_displayedProjects[index]);
      },
    );
  }

  Widget _buildProjectCard(Map<String, dynamic> project) {
    final projectId = project['id']?.toString();
    if (projectId == null) {
      return const SizedBox(); // Skip rendering invalid projects
    }

    return Card(
      elevation: 4,
      child: InkWell(
        onTap: () {
          Provider.of<AppState>(context, listen: false)
              .setCurrentProject(projectId);
          Navigator.pushReplacementNamed(
            context,
            '/home',
            arguments: projectId,
          );
        },
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      project['name']?.toString() ?? 'Untitled Project',
                      style: Theme.of(context).textTheme.titleMedium,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Row(
                    children: [
                      IconButton(
                        icon: const Icon(Icons.people),
                        onPressed: () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (context) => CollaborationScreen(
                                projectId: project['id'],
                                projectName: project['name'],
                              ),
                            ),
                          );
                        },
                        tooltip: 'Manage Collaborations',
                      ),
                      _buildUniverseDropdown(project),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Expanded(
                child: Text(
                  project['description']?.toString() ?? 'No description',
                  style: Theme.of(context).textTheme.bodyMedium,
                  overflow: TextOverflow.ellipsis,
                  maxLines: 3,
                ),
              ),
              const Spacer(),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Chapters: ${project['chapter_count']?.toString() ?? '0'}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  Text(
                    'Words: ${project['word_count']?.toString() ?? '0'}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildUniverseDropdown(Map<String, dynamic> project) {
    final projectId = project['id']?.toString();
    if (projectId == null) {
      return const SizedBox(); // Skip rendering for invalid projects
    }

    return FutureBuilder<List<dynamic>>(
      future: _fetchUniverses(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(strokeWidth: 2),
          );
        }

        final universes = snapshot.data ?? [];
        String currentUniverseId =
            project['universe_id']?.toString() ?? 'no_universe';

        return PopupMenuButton<String>(
          icon: Icon(
            Icons.public,
            color: currentUniverseId != 'no_universe'
                ? Theme.of(context).colorScheme.primary
                : Theme.of(context).colorScheme.onSurface.withOpacity(0.5),
          ),
          onSelected: (String newValue) {
            _updateProjectUniverse(
              projectId,
              newValue == 'no_universe' ? null : newValue,
            );
          },
          itemBuilder: (context) => [
            const PopupMenuItem<String>(
              value: 'no_universe',
              child: Text('No Universe'),
            ),
            ...universes.map((universe) {
              return PopupMenuItem<String>(
                value: universe['id'].toString(),
                child: Text(universe['name']),
              );
            }).toList(),
          ],
        );
      },
    );
  }

  Widget _buildDrawer() {
    return Drawer(
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          DrawerHeader(
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.primary,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Image.asset(
                  'assets/images/logo.png',
                  width: 48,
                  height: 48,
                  color: Colors.white,
                ),
                const SizedBox(height: 8),
                Text(
                  'ScrollWise AI',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                      ),
                ),
              ],
            ),
          ),
          ListTile(
            leading: const Icon(Icons.settings),
            title: const Text('Settings'),
            onTap: () {
              Navigator.pop(context); // Close the drawer
              Navigator.pushNamed(context, '/settings');
            },
          ),
          ListTile(
            leading: const Icon(Icons.folder),
            title: const Text('Projects'),
            onTap: () {
              Navigator.pop(context); // Close the drawer
            },
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.logout),
            title: const Text('Logout'),
            onTap: () async {
              await removeAuthToken();
              if (mounted) {
                Navigator.pushReplacementNamed(context, '/login');
              }
            },
          ),
        ],
      ),
    );
  }

  void _showProjectDialog() {
    // Reset the selected universe ID when opening the dialog
    _selectedUniverseId = 'no_universe';

    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Row(
            children: [
              Icon(Icons.create_new_folder,
                  color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 8),
              const Text('Create New Project'),
            ],
          ),
          content: SingleChildScrollView(
            child: Form(
              key: _projectFormKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextFormField(
                    controller: _projectNameController,
                    decoration: const InputDecoration(
                      labelText: 'Project Name',
                      prefixIcon: Icon(Icons.drive_file_rename_outline),
                    ),
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return 'Please enter a project name';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _projectDescriptionController,
                    decoration: const InputDecoration(
                      labelText: 'Project Description',
                      prefixIcon: Icon(Icons.description),
                    ),
                    maxLines: 3,
                  ),
                  const SizedBox(height: 16),
                  FutureBuilder<List<dynamic>>(
                    future: _fetchUniverses(),
                    builder: (context, snapshot) {
                      if (snapshot.connectionState == ConnectionState.waiting) {
                        return const CircularProgressIndicator();
                      }
                      final universes = snapshot.data ?? [];
                      return DropdownButtonFormField<String>(
                        // Changed to non-nullable String
                        value: _selectedUniverseId ??
                            'no_universe', // Default to 'no_universe'
                        decoration: const InputDecoration(
                          labelText: 'Universe (Optional)',
                          prefixIcon: Icon(Icons.public),
                        ),
                        items: [
                          const DropdownMenuItem<String>(
                            value: 'no_universe',
                            child: Text('No Universe'),
                          ),
                          ...universes.map((universe) {
                            return DropdownMenuItem<String>(
                              value: universe['id'].toString(),
                              child: Text(universe['name']),
                            );
                          }).toList(),
                        ],
                        onChanged: (String? value) {
                          setState(() {
                            _selectedUniverseId = value ?? 'no_universe';
                          });
                        },
                      );
                    },
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton.icon(
              icon: const Icon(Icons.close),
              label: const Text('Cancel'),
              onPressed: () => Navigator.of(context).pop(),
            ),
            ElevatedButton.icon(
              icon: const Icon(Icons.check),
              label: const Text('Create'),
              onPressed: () {
                if (_projectFormKey.currentState!.validate()) {
                  _createProject();
                  Navigator.of(context).pop();
                }
              },
            ),
          ],
        );
      },
    );
  }

  // Add empty state widgets
  Widget _buildEmptyProjectsState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.folder_off,
            size: 64,
            color: Theme.of(context).colorScheme.secondary.withOpacity(0.5),
          ),
          const SizedBox(height: 16),
          Text(
            'No Projects Found',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: Theme.of(context).colorScheme.secondary,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            'Create a new project to get started',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color:
                      Theme.of(context).colorScheme.onSurface.withOpacity(0.6),
                ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _showProjectDialog,
            icon: const Icon(Icons.add),
            label: const Text('Create Project'),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyUniversesState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.public_off,
            size: 64,
            color: Theme.of(context).colorScheme.secondary.withOpacity(0.5),
          ),
          const SizedBox(height: 16),
          Text(
            'No Universes Found',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: Theme.of(context).colorScheme.secondary,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            'Create a new universe to get started',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color:
                      Theme.of(context).colorScheme.onSurface.withOpacity(0.6),
                ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _showUniverseDialog,
            icon: const Icon(Icons.add),
            label: const Text('Create Universe'),
          ),
        ],
      ),
    );
  }

  Widget _buildCollaborationsTab() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_collaborations.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.people_outline,
              size: 64,
              color: Theme.of(context).colorScheme.secondary.withOpacity(0.5),
            ),
            const SizedBox(height: 16),
            Text(
              'No collaborations found',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: Theme.of(context).colorScheme.secondary,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              'Join a project using a collaboration token',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.secondary,
                  ),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              icon: const Icon(Icons.person_add),
              label: const Text('Join Collaboration'),
              onPressed: _showJoinCollaborationDialog,
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _collaborations.length,
      itemBuilder: (context, index) {
        final collaboration = _collaborations[index];
        return Card(
          elevation: 4,
          child: ListTile(
            leading: const Icon(Icons.folder_shared),
            title: Text(collaboration['project_name']),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Owner: ${collaboration['owner_name']}'),
                Text('Status: ${collaboration['status']}'),
                const SizedBox(height: 4),
                Wrap(
                  spacing: 4,
                  children:
                      (collaboration['permissions'] as Map<String, dynamic>)
                          .entries
                          .where((e) => e.value == true)
                          .map((e) => Chip(
                                label: Text(
                                  e.key.replaceAll('_', ' ').toUpperCase(),
                                  style: const TextStyle(fontSize: 10),
                                ),
                              ))
                          .toList(),
                ),
              ],
            ),
            trailing: PopupMenuButton(
              itemBuilder: (context) => [
                PopupMenuItem(
                  child: const Text('View Project'),
                  onTap: () {
                    Provider.of<AppState>(context, listen: false)
                        .setCurrentProject(collaboration['project_id']);
                    Navigator.pushReplacementNamed(
                      context,
                      '/home',
                      arguments: collaboration['project_id'],
                    );
                  },
                ),
                if (collaboration['status'] == 'active')
                  PopupMenuItem(
                    child: const Text('Leave Collaboration'),
                    onTap: () => _leaveCollaboration(collaboration['id']),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _showJoinCollaborationDialog() async {
    final token = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Join Collaboration'),
        content: const TextField(
          key: Key('token_field'),
          decoration: InputDecoration(
            labelText: 'Collaboration Token',
            hintText: 'Enter the token you received',
          ),
        ),
        actions: [
          TextButton(
            child: const Text('Cancel'),
            onPressed: () => Navigator.of(context).pop(),
          ),
          ElevatedButton(
            child: const Text('Join'),
            onPressed: () {
              String? token = _tokenFieldKey.currentState?.text;
              Navigator.of(context).pop(token);
            },
          ),
        ],
      ),
    );

    if (token != null && token.isNotEmpty) {
      try {
        final response = await http.post(
          Uri.parse('$apiUrl/collaborations/accept'),
          headers: {
            ...await getAuthHeaders(),
            'Content-Type': 'application/json',
          },
          body: json.encode({'access_token': token}),
        );

        if (response.statusCode == 200) {
          await _fetchCollaborations();
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                  content: Text('Successfully joined collaboration')),
            );
          }
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error joining collaboration: $e')),
          );
        }
      }
    }
  }

  Future<void> _leaveCollaboration(String collaborationId) async {
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/collaborations/$collaborationId'),
        headers: await getAuthHeaders(),
      );

      if (response.statusCode == 200) {
        await _fetchCollaborations();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Successfully left collaboration')),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error leaving collaboration: $e')),
        );
      }
    }
  }

  Widget _buildFloatingActionButton() {
    if (_tabController.index == 2) {
      // Collaborations tab
      return FloatingActionButton(
        onPressed: _showJoinCollaborationDialog,
        child: const Icon(Icons.person_add),
      );
    }

    return SpeedDial(
      icon: Icons.add,
      activeIcon: Icons.close,
      children: [
        SpeedDialChild(
          child: const Icon(Icons.folder_special),
          label: 'New Project',
          onTap: () => _showProjectDialog(),
        ),
        SpeedDialChild(
          child: const Icon(Icons.public),
          label: 'New Universe',
          onTap: () => _showUniverseDialog(),
        ),
      ],
    );
  }
}
