import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/collaboration.dart';
import '../utils/constants.dart';
import '../utils/auth.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class CollaborationScreen extends StatefulWidget {
  final String projectId;
  final String projectName;

  const CollaborationScreen({
    Key? key,
    required this.projectId,
    required this.projectName,
  }) : super(key: key);

  @override
  _CollaborationScreenState createState() => _CollaborationScreenState();
}

class _CollaborationScreenState extends State<CollaborationScreen> {
  List<Collaboration> _collaborations = [];
  bool _isLoading = true;
  final Map<String, bool> _defaultPermissions = {
    'read_chapters': true,
    'write_chapters': false,
    'manage_codex': false,
    'manage_knowledge_base': false,
  };

  @override
  void initState() {
    super.initState();
    _fetchCollaborations();
  }

  Future<void> _fetchCollaborations() async {
    setState(() => _isLoading = true);
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/collaborations/project/${widget.projectId}'),
        headers: await getAuthHeaders(),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() {
          _collaborations = (data['collaborations'] as List)
              .map((c) => Collaboration.fromJson(c))
              .toList();
        });
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error fetching collaborations: $e')),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _createCollaborationToken() async {
    final permissions = Map<String, bool>.from(_defaultPermissions);
    int expiresInDays = 30;

    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => _CollaborationDialog(
        initialPermissions: permissions,
        initialDays: expiresInDays,
      ),
    );

    if (result != null) {
      try {
        final response = await http.post(
          Uri.parse('$apiUrl/collaborations/${widget.projectId}/create-token'),
          headers: {
            ...await getAuthHeaders(),
            'Content-Type': 'application/json',
          },
          body: json.encode({
            'permissions': result['permissions'],
            'expires_in_days': result['expires_in_days'],
          }),
        );

        if (response.statusCode == 200) {
          final token = json.decode(response.body)['access_token'];
          _showTokenDialog(token);
          await _fetchCollaborations();
        }
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error creating collaboration token: $e')),
        );
      }
    }
  }

  Future<void> _showTokenDialog(String token) async {
    return showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Collaboration Token'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Share this token with your collaborator:'),
            const SizedBox(height: 16),
            SelectableText(
              token,
              style: const TextStyle(fontFamily: 'monospace'),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              icon: const Icon(Icons.copy),
              label: const Text('Copy to Clipboard'),
              onPressed: () {
                Clipboard.setData(ClipboardData(text: token));
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Token copied to clipboard')),
                );
              },
            ),
          ],
        ),
        actions: [
          TextButton(
            child: const Text('Close'),
            onPressed: () => Navigator.of(context).pop(),
          ),
        ],
      ),
    );
  }

  Future<void> _acceptCollaboration() async {
    final token = await showDialog<String>(
      context: context,
      builder: (context) => _TokenInputDialog(),
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
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Successfully joined collaboration')),
          );
          await _fetchCollaborations();
        }
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error accepting collaboration: $e')),
        );
      }
    }
  }

  Future<void> _revokeCollaboration(String collaborationId) async {
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/collaborations/$collaborationId'),
        headers: await getAuthHeaders(),
      );

      if (response.statusCode == 200) {
        await _fetchCollaborations();
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error revoking collaboration: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Collaborations - ${widget.projectName}'),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      ElevatedButton.icon(
                        icon: const Icon(Icons.add),
                        label: const Text('Create Collaboration'),
                        onPressed: _createCollaborationToken,
                      ),
                      ElevatedButton.icon(
                        icon: const Icon(Icons.person_add),
                        label: const Text('Join Collaboration'),
                        onPressed: _acceptCollaboration,
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: _collaborations.isEmpty
                      ? const Center(
                          child: Text('No collaborations found'),
                        )
                      : ListView.builder(
                          itemCount: _collaborations.length,
                          itemBuilder: (context, index) {
                            final collaboration = _collaborations[index];
                            return _CollaborationTile(
                              collaboration: collaboration,
                              onRevoke: () =>
                                  _revokeCollaboration(collaboration.id),
                            );
                          },
                        ),
                ),
              ],
            ),
    );
  }
}

class _CollaborationDialog extends StatefulWidget {
  final Map<String, bool> initialPermissions;
  final int initialDays;

  const _CollaborationDialog({
    Key? key,
    required this.initialPermissions,
    required this.initialDays,
  }) : super(key: key);

  @override
  _CollaborationDialogState createState() => _CollaborationDialogState();
}

class _CollaborationDialogState extends State<_CollaborationDialog> {
  late Map<String, bool> _permissions;
  late int _expiresInDays;

  @override
  void initState() {
    super.initState();
    _permissions = Map<String, bool>.from(widget.initialPermissions);
    _expiresInDays = widget.initialDays;
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Create Collaboration'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Permissions:'),
            ...widget.initialPermissions.keys.map((permission) {
              return CheckboxListTile(
                title: Text(permission.replaceAll('_', ' ').toUpperCase()),
                value: _permissions[permission],
                onChanged: (value) {
                  setState(() => _permissions[permission] = value!);
                },
              );
            }),
            const SizedBox(height: 16),
            Row(
              children: [
                const Text('Expires in:'),
                const SizedBox(width: 8),
                DropdownButton<int>(
                  value: _expiresInDays,
                  items: [7, 14, 30, 60, 90].map((days) {
                    return DropdownMenuItem(
                      value: days,
                      child: Text('$days days'),
                    );
                  }).toList(),
                  onChanged: (value) {
                    setState(() => _expiresInDays = value!);
                  },
                ),
              ],
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          child: const Text('Cancel'),
          onPressed: () => Navigator.of(context).pop(),
        ),
        ElevatedButton(
          child: const Text('Create'),
          onPressed: () => Navigator.of(context).pop({
            'permissions': _permissions,
            'expires_in_days': _expiresInDays,
          }),
        ),
      ],
    );
  }
}

class _TokenInputDialog extends StatefulWidget {
  @override
  _TokenInputDialogState createState() => _TokenInputDialogState();
}

class _TokenInputDialogState extends State<_TokenInputDialog> {
  final _tokenController = TextEditingController();

  @override
  void dispose() {
    _tokenController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Join Collaboration'),
      content: TextField(
        controller: _tokenController,
        decoration: const InputDecoration(
          labelText: 'Enter collaboration token',
          hintText: 'Paste the token here',
        ),
      ),
      actions: [
        TextButton(
          child: const Text('Cancel'),
          onPressed: () => Navigator.of(context).pop(),
        ),
        ElevatedButton(
          child: const Text('Join'),
          onPressed: () => Navigator.of(context).pop(_tokenController.text),
        ),
      ],
    );
  }
}

class _CollaborationTile extends StatelessWidget {
  final Collaboration collaboration;
  final VoidCallback onRevoke;

  const _CollaborationTile({
    Key? key,
    required this.collaboration,
    required this.onRevoke,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: ListTile(
        title: Text(collaboration.collaboratorId ?? 'Pending'),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Status: ${collaboration.status}'),
            Text(
              'Expires: ${collaboration.expiresAt?.toString() ?? 'Never'}',
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: collaboration.permissions.entries
                  .where((e) => e.value)
                  .map((e) => Chip(
                        label: Text(e.key.replaceAll('_', ' ').toUpperCase()),
                      ))
                  .toList(),
            ),
          ],
        ),
        trailing: collaboration.isActive
            ? IconButton(
                icon: const Icon(Icons.remove_circle_outline),
                color: Colors.red,
                onPressed: onRevoke,
              )
            : null,
      ),
    );
  }
}
