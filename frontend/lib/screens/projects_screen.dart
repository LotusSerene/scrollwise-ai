import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import 'package:fluttertoast/fluttertoast.dart';
import 'universe_screen.dart';
import 'dart:io';
import 'dart:async';

class ProjectsScreen extends StatefulWidget {
  const ProjectsScreen({Key? key}) : super(key: key);

  @override
  State<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends State<ProjectsScreen> {
  bool _mounted = true;
  bool _isLoading = true;
  List<dynamic> _projects = [];
  List<dynamic> _universes = [];
  final _projectFormKey = GlobalKey<FormState>();
  final _universeFormKey = GlobalKey<FormState>();
  final _projectNameController = TextEditingController();
  final _projectDescriptionController = TextEditingController();
  final _universeNameController = TextEditingController();
  String? _selectedUniverseId;

  @override
  void initState() {
    super.initState();
    _fetchData();
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
      Fluttertoast.showToast(msg: 'Error fetching data: ${error.toString()}');
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
          .timeout(Duration(seconds: 10)); // Add a timeout
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
      Fluttertoast.showToast(msg: 'Request timed out. Please try again.');
    } on SocketException catch (e) {
      print('Socket Exception: $e');
      if (!_mounted) return;
      Fluttertoast.showToast(
          msg: 'Network error. Please check your connection.');
    } catch (error) {
      print('Error fetching projects: $error');
      if (!_mounted) return;
      Fluttertoast.showToast(
          msg: 'Error fetching projects: ${error.toString()}');
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
        final requestBody = {
          'name': _projectNameController.text,
          'description': _projectDescriptionController.text,
          'universe_id': _selectedUniverseId,
        };
        final response = await http.post(
          Uri.parse('$apiUrl/projects'),
          headers: headers,
          body: utf8.encode(json.encode(requestBody)),
        );

        if (response.statusCode == 201) {
          final newProject = json.decode(utf8.decode(response.bodyBytes));
          setState(() {
            _projects.add(newProject);
            _projectNameController.clear();
            _projectDescriptionController.clear();
          });
          Fluttertoast.showToast(msg: 'Project created successfully');
        } else {
          final errorData = json.decode(response.body);
          throw Exception(errorData['detail'] ?? 'Unknown error occurred');
        }
      } catch (error) {
        print('Error creating project: $error');
        Fluttertoast.showToast(
            msg: 'Error creating project: ${error.toString()}');
      }
    }
  }

  Future<void> _createUniverse() async {
    if (_universeFormKey.currentState!.validate()) {
      try {
        final headers = {
          ...await getAuthHeaders(),
          'Content-Type': 'application/json',
        };
        final response = await http.post(
          Uri.parse('$apiUrl/universes'),
          headers: headers,
          body:
              utf8.encode(json.encode({'name': _universeNameController.text})),
        );

        if (response.statusCode == 201) {
          final newUniverse = json.decode(utf8.decode(response.bodyBytes));
          setState(() {
            _universes.add(newUniverse);
            _universeNameController.clear();
          });
          Fluttertoast.showToast(msg: 'Universe created successfully');
          _fetchUniverses(); // Refresh the list of universes
        } else {
          final errorData = json.decode(response.body);
          throw Exception(errorData['detail'] ?? 'Unknown error occurred');
        }
      } catch (error) {
        print('Error creating universe: $error');
        Fluttertoast.showToast(
            msg: 'Error creating universe: ${error.toString()}');
      }
    }
  }

  Future<void> _updateUniverse(String universeId, String newName) async {
    try {
      final response = await http.put(
        Uri.parse('$apiUrl/universes/$universeId'),
        headers: {
          ...await getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: utf8.encode(json.encode({
          'name': newName,
        })),
      );

      if (response.statusCode == 200) {
        Fluttertoast.showToast(msg: 'Universe updated successfully');
        _fetchUniverses(); // Refresh the list of universes
      } else {
        final errorData = json.decode(response.body);
        throw Exception(errorData['detail'] ?? 'Unknown error occurred');
      }
    } catch (error) {
      print('Error updating universe: $error');
      Fluttertoast.showToast(
          msg: 'Error updating universe: ${error.toString()}');
    }
  }

  Future<void> _deleteUniverse(String universeId) async {
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/universes/$universeId'),
        headers: await getAuthHeaders(),
      );

      if (response.statusCode == 200) {
        Fluttertoast.showToast(msg: 'Universe deleted successfully');
        _fetchUniverses(); // Refresh the list of universes
      } else {
        final errorData = json.decode(response.body);
        throw Exception(errorData['detail'] ?? 'Unknown error occurred');
      }
    } catch (error) {
      print('Error deleting universe: $error');
      Fluttertoast.showToast(
          msg: 'Error deleting universe: ${error.toString()}');
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
                    _universeNameController.text = controller.text;
                    _createUniverse();
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
        body: utf8.encode(json.encode({'universe_id': universeId})),
      );

      if (response.statusCode == 200) {
        Fluttertoast.showToast(msg: 'Project updated successfully');
        _fetchProjects(); // Refresh the list of projects
      } else {
        throw Exception('Failed to update project');
      }
    } catch (error) {
      print('Error updating project universe: $error');
      Fluttertoast.showToast(
          msg: 'Error updating project: ${error.toString()}');
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Builder(
        builder: (BuildContext context) {
          return Scaffold(
            appBar: AppBar(
              title: const Text('Projects & Universes'),
              bottom: const TabBar(
                tabs: [
                  Tab(text: 'Projects'),
                  Tab(text: 'Universes'),
                ],
              ),
            ),
            body: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : TabBarView(
                    children: [
                      _buildProjectsTab(),
                      _buildUniversesTab(),
                    ],
                  ),
            floatingActionButton: FloatingActionButton(
              onPressed: () {
                final TabController tabController =
                    DefaultTabController.of(context);
                if (tabController.index == 0) {
                  // Show project creation form
                  _showProjectDialog();
                } else {
                  // Show universe creation dialog
                  _showUniverseDialog();
                }
              },
              child: const Icon(Icons.add),
            ),
            bottomNavigationBar: BottomNavigationBar(
              items: const <BottomNavigationBarItem>[
                BottomNavigationBarItem(
                  icon: Icon(Icons.folder),
                  label: 'Projects',
                ),
                BottomNavigationBarItem(
                  icon: Icon(Icons.settings),
                  label: 'Settings',
                ),
              ],
              currentIndex: 0,
              onTap: (index) {
                if (index == 1) {
                  Navigator.pushNamed(context, '/settings');
                }
              },
            ),
            drawer: _buildDrawer(),
          );
        },
      ),
    );
  }

  Widget _buildProjectsTab() {
    return _projects.isEmpty
        ? const Center(child: Text('No projects found.'))
        : ListView.builder(
            itemCount: _projects.length,
            itemBuilder: (context, index) {
              final project = _projects[index];
              return ListTile(
                title: Text(project['name']),
                subtitle: Text(project['description']),
                trailing: FutureBuilder<List<dynamic>>(
                  future: _fetchUniverses(),
                  builder: (context, snapshot) {
                    if (snapshot.connectionState == ConnectionState.waiting) {
                      return const CircularProgressIndicator();
                    } else if (snapshot.hasError) {
                      return Text('Error: ${snapshot.error}');
                    } else {
                      final universes = snapshot.data!;
                      return DropdownButton<String>(
                        value: project['universe_id'],
                        onChanged: (String? newValue) {
                          _updateProjectUniverse(project['id'], newValue);
                        },
                        items: [
                          const DropdownMenuItem<String>(
                            value: null,
                            child: Text('No Universe'),
                          ),
                          ...universes.map((universe) {
                            return DropdownMenuItem<String>(
                              value: universe['id'],
                              child: Text(universe['name']),
                            );
                          }).toList(),
                        ],
                      );
                    }
                  },
                ),
                onTap: () {
                  Provider.of<AppState>(context, listen: false)
                      .setCurrentProject(project['id']);
                  Navigator.pushReplacementNamed(context, '/home',
                      arguments: project['id']);
                },
              );
            },
          );
  }

  Widget _buildUniversesTab() {
    return _universes.isEmpty
        ? const Center(child: Text('No universes found.'))
        : ListView.builder(
            itemCount: _universes.length,
            itemBuilder: (context, index) {
              final universe = _universes[index];
              return ListTile(
                title: Text(universe['name']),
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) =>
                          UniverseScreen(universeId: universe['id']),
                    ),
                  );
                },
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      icon: const Icon(Icons.edit),
                      onPressed: () {
                        _showUniverseDialog(
                          universeId: universe['id'],
                          universeName: universe['name'],
                        );
                      },
                    ),
                    IconButton(
                      icon: const Icon(Icons.delete),
                      onPressed: () {
                        _deleteUniverse(universe['id']);
                      },
                    ),
                  ],
                ),
              );
            },
          );
  }

  void _showProjectDialog() {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('Create Project'),
          content: Form(
            key: _projectFormKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextFormField(
                  controller: _projectNameController,
                  decoration: const InputDecoration(labelText: 'Project Name'),
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return 'Please enter a project name';
                    }
                    return null;
                  },
                ),
                TextFormField(
                  controller: _projectDescriptionController,
                  decoration:
                      const InputDecoration(labelText: 'Project Description'),
                ),
                FutureBuilder<List<dynamic>>(
                  future: _fetchUniverses(),
                  builder: (context, snapshot) {
                    if (snapshot.connectionState == ConnectionState.waiting) {
                      return const CircularProgressIndicator();
                    } else if (snapshot.hasError) {
                      return Text('Error: ${snapshot.error}');
                    } else {
                      final universes = snapshot.data!;
                      return DropdownButtonFormField<String>(
                        value: _selectedUniverseId,
                        onChanged: (value) {
                          setState(() {
                            _selectedUniverseId = value;
                          });
                        },
                        items: universes.map((universe) {
                          return DropdownMenuItem<String>(
                            value: universe['id'],
                            child: Text(universe['name']),
                          );
                        }).toList(),
                        decoration:
                            const InputDecoration(labelText: 'Universe'),
                        validator: (value) {
                          if (value == null || value.isEmpty) {
                            return 'Please select a universe';
                          }
                          return null;
                        },
                      );
                    }
                  },
                ),
              ],
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
              child: const Text('Create'),
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

  Widget _buildDrawer() {
    return Drawer(
      child: ListView(
        padding: EdgeInsets.zero,
        children: <Widget>[
          const DrawerHeader(
            decoration: BoxDecoration(
              color: Colors.blue,
            ),
            child: Text(
              'Menu',
              style: TextStyle(
                color: Colors.white,
                fontSize: 24,
              ),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.settings),
            title: const Text('Settings'),
            onTap: () {
              Navigator.pushNamed(context, '/settings');
            },
          ),
          ListTile(
            leading: const Icon(Icons.folder),
            title: const Text('Projects'),
            onTap: () {
              Navigator.pop(context);
            },
          ),
          ListTile(
            leading: const Icon(Icons.logout),
            title: const Text('Logout'),
            onTap: () {
              // Handle logout functionality
            },
          ),
        ],
      ),
    );
  }
}
