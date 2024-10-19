import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:provider/provider.dart'; // Import provider
import '../providers/app_state.dart'; // Import AppState
import 'package:fluttertoast/fluttertoast.dart';

class ProjectsScreen extends StatefulWidget {
  const ProjectsScreen({Key? key}) : super(key: key);

  @override
  State<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends State<ProjectsScreen> {
  List<dynamic> _projects = [];
  bool _isLoading = true;
  final _formKey = GlobalKey<FormState>();
  final _projectNameController = TextEditingController();
  final _projectDescriptionController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _fetchProjects();
  }

  Future<void> _fetchProjects() async {
    setState(() {
      _isLoading = true;
    });
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/projects'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 200) {
        setState(() {
          _projects = json.decode(response.body)['projects'];
          _isLoading = false;
        });
      } else {
        throw Exception('Failed to load projects');
      }
    } catch (error) {
      print('Error fetching projects: $error');
      Fluttertoast.showToast(msg: 'Error fetching projects');
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _createProject() async {
    if (_formKey.currentState!.validate()) {
      try {
        final response = await http.post(
          Uri.parse('$apiUrl/projects'),
          headers: {
            ...await getAuthHeaders(),
            'Content-Type': 'application/json',
          },
          body: json.encode({
            'name': _projectNameController.text,
            'description': _projectDescriptionController.text,
          }),
        );

        if (response.statusCode == 201) {
          final newProject = json.decode(response.body);
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
        Fluttertoast.showToast(msg: 'Error creating project: ${error.toString()}');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Projects')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Form(
                    key: _formKey,
                    child: Column(
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
                        ElevatedButton(
                          onPressed: _createProject,
                          child: const Text('Create Project'),
                        ),
                      ],
                    ),
                  ),
                ),
                Expanded(
                  child: ListView.builder(
                    itemCount: _projects.length,
                    itemBuilder: (context, index) {
                      final project = _projects[index];
                      return ListTile(
                        title: Text(project['name']),
                        subtitle: Text(project['description']),
                        onTap: () {
                          // Correctly pass projectId as a string
                          Provider.of<AppState>(context, listen: false)
                              .setCurrentProject(project['id']); // Update AppState
                          Navigator.pushReplacementNamed(context, '/home',
                              arguments: project['id']); // Pass projectId as string
                        },
                      );
                    },
                  ),
                ),
              ],
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
        currentIndex: 1, // Set initial index to projects
        onTap: (index) {
          if (index == 1) {
            Navigator.pushNamed(context, '/settings');
          }
        },
      ),
      drawer: Drawer(
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
            InkWell(
              onTap: () {
                Navigator.pushNamed(context, '/settings');
              },
              child: const ListTile(
                leading: Icon(Icons.settings),
                title: Text('Settings'),
              ),
            ),
            InkWell(
              onTap: () {
                //This should not be necessary, as we are already on the projects screen
              },

              child: const ListTile(
                leading: Icon(Icons.folder),
                title: Text('Projects'),
              ),
            ),

            InkWell(
              onTap: () {
                // Handle logout functionality
              },
              child: const ListTile(
                leading: Icon(Icons.logout),
                title: Text('Logout'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
