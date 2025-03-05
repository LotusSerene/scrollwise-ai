import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import 'package:logging/logging.dart';

final _logger = Logger('ProjectSettings');

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
      _logger.severe('Error fetching project data: $error');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Error fetching project data')));
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
        if (!mounted) return;

        if (response.statusCode == 200) {
          ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Project updated successfully')));
        } else {
          final errorData = json.decode(response.body);
          throw Exception(errorData['detail'] ?? 'Unknown error occurred');
        }
      } catch (error) {
        _logger.severe('Error updating project: $error');
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text('Error updating project: ${error.toString()}')));
      } finally {
        if (mounted) {
          setState(() {
            _isLoading = false;
          });
        }
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
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Project deleted successfully')));
        Provider.of<AppState>(context, listen: false).setCurrentProject(null);
        Navigator.pushReplacementNamed(context, '/projects');
      } else {
        throw Exception('Failed to delete project');
      }
    } catch (error) {
      _logger.severe('Error deleting project: $error');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Error deleting project')));
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _refreshKnowledgeBase() async {
    if (await showDialog(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Refresh Knowledge Base'),
            content: const Text(
                'This will rebuild the entire knowledge base for this project. This may take a few minutes. Are you sure?'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Cancel'),
              ),
              TextButton(
                onPressed: () {
                  Navigator.pop(context, true);
                },
                child: const Text('Refresh'),
              ),
            ],
          ),
        ) !=
        true) {
      return;
    }

    setState(() {
      _isLoading = true;
    });

    try {
      final response = await http.post(
        Uri.parse(
            '$apiUrl/projects/${widget.projectId}/refresh-knowledge-base'),
        headers: await getAuthHeaders(),
      );

      if (!mounted) return;

      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text('Knowledge base refreshed successfully')),
        );
      } else {
        throw Exception('Failed to refresh knowledge base');
      }
    } catch (error) {
      _logger.severe('Error refreshing knowledge base: $error');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Error refreshing knowledge base')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildHeader(),
                  const SizedBox(height: 32),
                  Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildSettingsSection(),
                        const SizedBox(height: 32),
                        _buildDangerZone(),
                      ],
                    ),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _buildHeader() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.settings,
              size: 32,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(width: 16),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Project Settings',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                Text(
                  'Configure your project preferences',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context)
                            .colorScheme
                            .onSurface
                            .withOpacity(0.6),
                      ),
                ),
              ],
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildSettingsSection() {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: Theme.of(context).colorScheme.outline.withOpacity(0.2),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'General Settings',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: Theme.of(context).colorScheme.primary,
                  ),
            ),
            const SizedBox(height: 24),
            TextFormField(
              controller: _projectNameController,
              decoration: InputDecoration(
                labelText: 'Project Name',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
                prefixIcon: const Icon(Icons.drive_file_rename_outline),
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
              decoration: InputDecoration(
                labelText: 'Project Description',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
                prefixIcon: const Icon(Icons.description),
              ),
              maxLines: 3,
            ),
            const SizedBox(height: 24),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton.icon(
                onPressed: _updateProject,
                icon: const Icon(Icons.save),
                label: const Text('Save Changes'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDangerZone() {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: Theme.of(context).colorScheme.error.withOpacity(0.2),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.warning,
                  color: Theme.of(context).colorScheme.error,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Text(
                  'Danger Zone',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: Theme.of(context).colorScheme.error,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Text(
              'Once you delete a project, there is no going back. Please be certain.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context)
                        .colorScheme
                        .onSurface
                        .withOpacity(0.6),
                  ),
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: _refreshKnowledgeBase,
              icon: const Icon(Icons.refresh),
              label: const Text('Refresh Knowledge Base'),
              style: OutlinedButton.styleFrom(
                foregroundColor: Theme.of(context).colorScheme.error,
                side: BorderSide(
                  color: Theme.of(context).colorScheme.error,
                ),
              ),
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: _deleteProject,
              icon: const Icon(Icons.delete_forever),
              label: const Text('Delete Project'),
              style: OutlinedButton.styleFrom(
                foregroundColor: Theme.of(context).colorScheme.error,
                side: BorderSide(
                  color: Theme.of(context).colorScheme.error,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
