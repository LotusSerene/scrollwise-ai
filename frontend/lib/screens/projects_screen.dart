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

class ProjectsScreen extends StatefulWidget {
  const ProjectsScreen({Key? key}) : super(key: key);

  @override
  State<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends State<ProjectsScreen>
    with SingleTickerProviderStateMixin {
  bool _mounted = true;
  bool _isLoading = true;
  List<dynamic> _projects = [];
  final List<dynamic> _universes = [];
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
    _tabController = TabController(length: 2, vsync: this);
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
    super.dispose();
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
    setState(() {
      _isLoading = true;
    });
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
        setState(() {
          _projects = json.decode(utf8.decode(response.bodyBytes))['projects'];
        });
      } else {
        throw Exception('Failed to load projects: ${response.statusCode}');
      }
    } on TimeoutException catch (e) {
      print('Timeout Exception: $e');
      if (!_mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Request timed out. Please try again.'),
          behavior: SnackBarBehavior.fixed, // Use fixed instead of floating
        ),
      );
    } on SocketException catch (e) {
      print('Socket Exception: $e');
      if (!_mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Network error. Please check your connection.'),
          behavior: SnackBarBehavior.fixed, // Use fixed instead of floating
        ),
      );
    } catch (error) {
      print('Error fetching projects: $error');
      if (!_mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error fetching projects: ${error.toString()}'),
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

  Future<void> _createProject() async {
    if (_projectFormKey.currentState!.validate()) {
      try {
        final headers = {
          ...await getAuthHeaders(),
          'Content-Type': 'application/json',
        };

        // Only include universe_id in the request body if it's not 'no_universe'
        final requestBody = {
          'name': _projectNameController.text,
          'description': _projectDescriptionController.text,
          if (_selectedUniverseId != 'no_universe')
            'universe_id': _selectedUniverseId,
        };

        final response = await http.post(
          Uri.parse('$apiUrl/projects'),
          headers: headers,
          body: utf8.encode(json.encode(requestBody)),
        );

        if (response.statusCode == 201 || response.statusCode == 200) {
          final newProject = json.decode(utf8.decode(response.bodyBytes));
          setState(() {
            _projects.add(newProject);
            _projectNameController.clear();
            _projectDescriptionController.clear();
            _selectedUniverseId = null;
          });
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Project created successfully'),
              behavior: SnackBarBehavior.fixed, // Use fixed instead of floating
            ),
          );
        } else {
          final errorData = json.decode(response.body);
          throw Exception(errorData['detail'] ?? 'Unknown error occurred');
        }
      } catch (error) {
        print('Error creating project: $error');
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error creating project: ${error.toString()}'),
            behavior: SnackBarBehavior.fixed, // Use fixed instead of floating
          ),
        );
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
        // Simplified body handling - always send null when universeId is null
        body: utf8.encode(json.encode({'universe_id': universeId})),
      );

      if (response.statusCode == 200) {
        setState(() {
          final projectIndex =
              _projects.indexWhere((p) => p['id'] == projectId);
          if (projectIndex != -1) {
            // Update the local project data
            _projects[projectIndex] = {
              ..._projects[projectIndex],
              'universe_id': universeId, // Directly use universeId
            };
          }
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Project updated successfully'),
            behavior: SnackBarBehavior.fixed, // Use fixed instead of floating
          ),
        );
      } else {
        throw Exception('Failed to update project');
      }
    } catch (error) {
      print('Error updating project universe: $error');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error updating project: ${error.toString()}'),
          behavior: SnackBarBehavior.fixed, // Use fixed instead of floating
        ),
      );
    }
  }

  // Add these new methods for universe management
  Widget _buildUniversesTab() {
    return Stack(
      children: [
        FutureBuilder<List<dynamic>>(
          future: _fetchUniverses(),
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }

            final universes = snapshot.data ?? [];

            if (universes.isEmpty) {
              return Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.public_off,
                      size: 64,
                      color: Theme.of(context)
                          .colorScheme
                          .secondary
                          .withOpacity(0.5),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'No universes found',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            color: Theme.of(context).colorScheme.secondary,
                          ),
                    ),
                  ],
                ),
              );
            }

            return GridView.builder(
              padding: const EdgeInsets.all(16),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                childAspectRatio: 1.3,
                crossAxisSpacing: 16,
                mainAxisSpacing: 16,
              ),
              itemCount: universes.length,
              itemBuilder: (context, index) {
                final universe = universes[index];
                return Card(
                  elevation: 4,
                  child: InkWell(
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) =>
                              UniverseScreen(universeId: universe['id']),
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
                                  style:
                                      Theme.of(context).textTheme.titleMedium,
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
                                    onTap: () =>
                                        _deleteUniverse(universe['id']),
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
              },
            );
          },
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
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
            ],
          ),
        ),
        floatingActionButton: SpeedDial(
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
        ),
        body: TabBarView(
          controller: _tabController,
          children: [
            _buildProjectsTab(),
            _buildUniversesTab(),
          ],
        ),
      ),
    );
  }

  Widget _buildProjectsTab() {
    return _projects.isEmpty
        ? Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  Icons.folder_open,
                  size: 64,
                  color:
                      Theme.of(context).colorScheme.secondary.withOpacity(0.5),
                ),
                const SizedBox(height: 16),
                Text(
                  'No projects found',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: Theme.of(context).colorScheme.secondary,
                      ),
                ),
              ],
            ),
          )
        : GridView.builder(
            padding: const EdgeInsets.all(16),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              childAspectRatio: 1.3,
              crossAxisSpacing: 16,
              mainAxisSpacing: 16,
            ),
            itemCount: _projects.length,
            itemBuilder: (context, index) {
              // Cast the dynamic map to Map<String, dynamic>
              final project = Map<String, dynamic>.from(_projects[index]);
              return Card(
                elevation: 4,
                child: InkWell(
                  onTap: () {
                    Provider.of<AppState>(context, listen: false)
                        .setCurrentProject(project['id']);
                    Navigator.pushReplacementNamed(context, '/home',
                        arguments: project['id']);
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
                                project['name'],
                                style: Theme.of(context).textTheme.titleMedium,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            _buildUniverseDropdown(
                                project), // Now passing properly typed Map
                          ],
                        ),
                        const SizedBox(height: 8),
                        Expanded(
                          child: Text(
                            project['description'] ?? 'No description',
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
                              'Chapters: ${project['chapter_count'] ?? 0}',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                            Text(
                              'Words: ${project['word_count'] ?? 0}',
                              style: Theme.of(context).textTheme.bodySmall,
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

  Widget _buildUniverseDropdown(Map<String, dynamic> project) {
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
        // Fix the syntax error in handling universe_id
        String? currentUniverseId = project['universe_id']?.toString();

        return PopupMenuButton<String?>(
          icon: Icon(
            Icons.public,
            color: currentUniverseId != null
                ? Theme.of(context).colorScheme.primary
                : Theme.of(context).colorScheme.onSurface.withOpacity(0.5),
          ),
          onSelected: (String? newValue) {
            if (newValue == 'no_universe') {
              _updateProjectUniverse(project['id'].toString(), null);
            } else {
              _updateProjectUniverse(project['id'].toString(), newValue);
            }
          },
          itemBuilder: (context) => [
            const PopupMenuItem<String?>(
              value: 'no_universe',
              child: Text('No Universe'),
            ),
            ...universes.map((universe) {
              return PopupMenuItem<String?>(
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
}
