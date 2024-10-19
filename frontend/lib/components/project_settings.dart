import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import 'package:fluttertoast/fluttertoast.dart';

class ProjectSettings extends StatefulWidget {
  final String projectId;

  const ProjectSettings({Key? key, required this.projectId}) : super(key: key);

  @override
  State<ProjectSettings> createState() => _ProjectSettingsState();
}

class _ProjectSettingsState extends State<ProjectSettings> {
  final _formKey = GlobalKey<FormState>();
  final _projectNameController = TextEditingController();
  final _projectDescriptionController = TextEditingController();
  bool _isLoading = false;
  String? _universeId;

  @override
  void initState() {
    super.initState();
    _fetchProjectData();
  }

  Future<void> _fetchProjectData() async {
    setState(() {
      _isLoading = true;
    });
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/projects/${widget.projectId}'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 200) {
        final projectData = json.decode(utf8.decode(response.bodyBytes));
        setState(() {
          _projectNameController.text = projectData['name'];
          _projectDescriptionController.text = projectData['description'];
          _universeId = projectData['universe_id'];
          _isLoading = false;
        });
      } else {
        throw Exception('Failed to load project data');
      }
    } catch (error) {
      print('Error fetching project data: $error');
      Fluttertoast.showToast(msg: 'Error fetching project data');
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _updateProject() async {
    if (_formKey.currentState!.validate()) {
      setState(() {
        _isLoading = true;
      });
      try {
        final response = await http.put(
          Uri.parse('$apiUrl/projects/${widget.projectId}'),
          headers: {
            ...await getAuthHeaders(),
            'Content-Type': 'application/json',
          },
          body: utf8.encode(json.encode({
            'name': _projectNameController.text,
            'description': _projectDescriptionController.text,
            'universe_id': _universeId,
          })),
        );
        if (response.statusCode == 200) {
          Fluttertoast.showToast(msg: 'Project updated successfully');
        } else {
          final errorData = json.decode(response.body);
          throw Exception(errorData['detail'] ?? 'Unknown error occurred');
        }
      } catch (error) {
        print('Error updating project: $error');
        Fluttertoast.showToast(
            msg: 'Error updating project: ${error.toString()}');
      } finally {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _deleteProject() async {
    if (await showDialog(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Delete Project'),
            content:
                const Text('Are you sure you want to delete this project?'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Cancel'),
              ),
              TextButton(
                onPressed: () async {
                  Navigator.pop(context);
                  await _performDelete();
                },
                child: const Text('Delete'),
              ),
            ],
          ),
        ) ==
        null) {
      return;
    }
  }

  Future<void> _performDelete() async {
    setState(() {
      _isLoading = true;
    });
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/projects/${widget.projectId}'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 200) {
        Fluttertoast.showToast(msg: 'Project deleted successfully');
        Provider.of<AppState>(context, listen: false).setCurrentProject(null);
        Navigator.pushReplacementNamed(context, '/projects');
      } else {
        throw Exception('Failed to delete project');
      }
    } catch (error) {
      print('Error deleting project: $error');
      Fluttertoast.showToast(msg: 'Error deleting project');
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Project Settings')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Padding(
              padding: const EdgeInsets.all(16.0),
              child: Form(
                key: _formKey,
                child: Column(
                  children: [
                    TextFormField(
                      controller: _projectNameController,
                      decoration:
                          const InputDecoration(labelText: 'Project Name'),
                      validator: (value) {
                        if (value == null || value.isEmpty) {
                          return 'Please enter a project name';
                        }
                        return null;
                      },
                    ),
                    TextFormField(
                      controller: _projectDescriptionController,
                      decoration: const InputDecoration(
                          labelText: 'Project Description'),
                    ),
                    ElevatedButton(
                      onPressed: _updateProject,
                      child: const Text('Update Project'),
                    ),
                    ElevatedButton(
                      onPressed: _deleteProject,
                      child: const Text('Delete Project'),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
