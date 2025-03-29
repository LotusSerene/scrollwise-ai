import 'package:flutter/material.dart';
import '../utils/auth.dart';
import '../models/character.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/constants.dart';
import 'package:expandable/expandable.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import 'package:logging/logging.dart';

final _logger = Logger('CharacterJourneyScreen');

class CharacterJourneyScreen extends StatefulWidget {
  final String projectId;

  const CharacterJourneyScreen({Key? key, required this.projectId})
      : super(key: key);

  @override
  State<CharacterJourneyScreen> createState() => _CharacterJourneyScreenState();
}

class _CharacterJourneyScreenState extends State<CharacterJourneyScreen> {
  List<Character> characters = [];
  bool isLoading = false;

  @override
  void initState() {
    super.initState();
    final appState = Provider.of<AppState>(context, listen: false);
    final savedState = appState.characterJourneyState;

    // Restore any previously updated characters
    if (savedState['lastGeneratedItem'] != null) {
      final updatedCharacters =
          savedState['lastGeneratedItem']['updatedCharacters'] as List<dynamic>;
      characters =
          updatedCharacters.map((json) => Character.fromJson(json)).toList();
    }

    _loadCharacters();
  }

  Future<void> _loadCharacters() async {
    setState(() => isLoading = true);
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/projects/${widget.projectId}/codex/characters'),
        headers: headers,
      );
      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body)['characters'];
        setState(() {
          characters = data.map((json) => Character.fromJson(json)).toList();
        });
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error loading characters: $e')),
      );
    } finally {
      setState(() => isLoading = false);
    }
  }

  Future<void> _updateCharacterInformation() async {
    final appState = Provider.of<AppState>(context, listen: false);
    final ignoredCharacters =
        appState.characterJourneyState['ignoredCharacters'] as Set<String>;
    appState.updateCharacterJourneyProgress(isGenerating: true);

    try {
      final headers = await getAuthHeaders();
      headers['Content-Type'] = 'application/json';

      bool anyUpdates = false;
      List<Map<String, dynamic>> updatedCharacters = [];

      for (var character in characters) {
        if (!ignoredCharacters.contains(character.id)) {
          final response = await http.post(
            Uri.parse('$apiUrl/projects/${widget.projectId}/codex/characters/${character.id}/extract-backstory'),
            headers: headers,
            body: json.encode({
              'character_id': character.id,
              'chapter_id': 'latest',
            }),
          );

          if (response.statusCode == 200) {
            final responseBody = json.decode(response.body);
            if (responseBody != null && responseBody['backstory'] != null) {
              setState(() {
                final index =
                    characters.indexWhere((c) => c.id == character.id);
                if (index != -1) {
                  characters[index] = characters[index].copyWith(
                    backstory: responseBody['backstory']['new_backstory'],
                  );
                  updatedCharacters.add(characters[index].toJson());
                }
              });
              anyUpdates = true;
            }
          }
        }
      }

      appState.updateCharacterJourneyProgress(
        isGenerating: false,
        lastGeneratedItem: {
          'updatedCharacters': updatedCharacters,
          'ignoredCharacters': List<String>.from(ignoredCharacters),
        },
      );

      if (anyUpdates) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Character information updated')),
        );
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No new information found')),
        );
      }
    } catch (e) {
      appState.updateCharacterJourneyProgress(isGenerating: false);
      _logger.severe('Error updating character information: $e');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error updating character information: $e')),
      );
    }
  }

  Future<void> _deleteBackstory(String characterId) async {
    setState(() => isLoading = true);
    try {
      final headers = await getAuthHeaders();
      final response = await http.delete(
        Uri.parse('$apiUrl/projects/${widget.projectId}/codex-items/characters/$characterId/backstory'),
        headers: headers,
      );
      if (response.statusCode == 200) {
        setState(() {
          final index = characters.indexWhere((c) => c.id == characterId);
          if (index != -1) {
            characters[index] = characters[index].copyWith(backstory: '');
          }
        });
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Backstory deleted successfully')),
        );
      } else {
        throw Exception('Failed to delete backstory');
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error deleting backstory: $e')),
      );
    } finally {
      if (mounted) {
        setState(() => isLoading = false);
      }
    }
  }

  Future<void> _editBackstory(Character character) async {
    final TextEditingController backstoryController =
        TextEditingController(text: character.backstory);

    final String? result = await showDialog<String>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text('Edit Backstory for ${character.name}'),
          content: TextField(
            controller: backstoryController,
            maxLines: null,
            decoration: const InputDecoration(
              hintText: 'Enter backstory...',
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context, backstoryController.text),
              child: const Text('Save'),
            ),
          ],
        );
      },
    );

    if (result != null) {
      setState(() => isLoading = true);
      try {
        final headers = await getAuthHeaders();
        headers['Content-Type'] = 'application/json';
        final response = await http.put(
          Uri.parse('$apiUrl/projects/${widget.projectId}/codex-items/characters/${character.id}/backstory'),
          headers: headers,
          body: json.encode(result), // Change this line
        );

        if (response.statusCode == 200) {
          setState(() {
            final index = characters.indexWhere((c) => c.id == character.id);
            if (index != -1) {
              characters[index] = characters[index].copyWith(backstory: result);
            }
          });
          if (!mounted) return;
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Backstory updated successfully')),
          );
        } else {
          _logger.severe('Error updating backstory: ${response.body}');
          if (!mounted) return;
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
                content: Text('Error updating backstory: ${response.body}')),
          );
        }
      } catch (e) {
        _logger.severe('Error updating backstory: $e');
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error updating backstory: $e')),
        );
      } finally {
        setState(() => isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        return Scaffold(
          body: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildHeader(),
                const SizedBox(height: 24),
                Expanded(
                  child: _buildCharacterList(),
                ),
              ],
            ),
          ),
          floatingActionButton: _buildUpdateButton(appState),
        );
      },
    );
  }

  Widget _buildHeader() {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        final ignoredCharacters =
            appState.characterJourneyState['ignoredCharacters'] as Set<String>;

        return Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Character Journey',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 16),
                Text(
                  '${characters.length} Characters | ${characters.length - ignoredCharacters.length} Active',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.primary,
                      ),
                ),
              ],
            ),
          ],
        );
      },
    );
  }

  Widget _buildCharacterList() {
    if (isLoading) {
      return const Center(
        child: CircularProgressIndicator(),
      );
    }

    if (characters.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.person_off,
              size: 64,
              color: Theme.of(context).colorScheme.onSurface.withOpacity(0.2),
            ),
            const SizedBox(height: 16),
            Text(
              'No Characters Found',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: Theme.of(context)
                        .colorScheme
                        .onSurface
                        .withOpacity(0.5),
                  ),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      itemCount: characters.length,
      itemBuilder: (context, index) {
        final character = characters[index];
        return _buildCharacterCard(character);
      },
    );
  }

  Widget _buildCharacterCard(Character character) {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        final ignoredCharacters =
            appState.characterJourneyState['ignoredCharacters'] as Set<String>;
        final isIgnored = ignoredCharacters.contains(character.id);

        return Card(
          margin: const EdgeInsets.only(bottom: 16),
          elevation: isIgnored ? 0 : 2,
          child: ExpandablePanel(
            theme: ExpandableThemeData(
              headerAlignment: ExpandablePanelHeaderAlignment.center,
              iconColor: Theme.of(context).colorScheme.primary,
              iconSize: 28,
            ),
            header: ListTile(
              leading: Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(8),
                  color: isIgnored
                      ? Theme.of(context).colorScheme.surfaceContainerHighest
                      : Theme.of(context).colorScheme.primary,
                ),
                child: Center(
                  child: Text(
                    character.name.substring(0, 1).toUpperCase(),
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          color: Colors
                              .white, // Changed to white for better contrast
                          fontWeight: FontWeight.bold, // Added bold weight
                        ),
                  ),
                ),
              ),
              title: Text(
                character.name,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: isIgnored
                          ? Theme.of(context)
                              .colorScheme
                              .onSurface
                              .withOpacity(0.5)
                          : Theme.of(context).colorScheme.onSurface,
                    ),
              ),
              trailing: Switch.adaptive(
                value: !isIgnored,
                onChanged: (value) {
                  final newIgnoredCharacters =
                      Set<String>.from(ignoredCharacters);
                  if (value) {
                    newIgnoredCharacters.remove(character.id);
                  } else {
                    newIgnoredCharacters.add(character.id);
                  }
                  appState.updateCharacterJourneyProgress(
                    ignoredCharacters: newIgnoredCharacters,
                  );
                },
                thumbColor: WidgetStateProperty.resolveWith((states) {
                  if (states.contains(WidgetState.hovered)) {
                    return Theme.of(context).colorScheme.onPrimary;
                  }
                  return null;
                }),
              ),
            ),
            collapsed: Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              child: Text(
                character.description,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context)
                          .colorScheme
                          .onSurface
                          .withOpacity(0.7),
                    ),
              ),
            ),
            expanded: _buildExpandedContent(character),
          ),
        );
      },
    );
  }

  Widget _buildExpandedContent(Character character) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSection(
            title: 'Description',
            content: character.description,
          ),
          const SizedBox(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Backstory',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              Row(
                children: [
                  IconButton(
                    icon: const Icon(Icons.edit),
                    tooltip: 'Edit Backstory',
                    onPressed: () => _editBackstory(character),
                  ),
                  IconButton(
                    icon: const Icon(Icons.delete),
                    tooltip: 'Delete Backstory',
                    onPressed: () => _showDeleteConfirmation(character),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            character.backstory.isNotEmpty
                ? character.backstory
                : 'No backstory available yet',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: character.backstory.isEmpty
                      ? Theme.of(context).colorScheme.onSurface.withOpacity(0.5)
                      : null,
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildSection({required String title, required String content}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        Text(content),
      ],
    );
  }

  void _showDeleteConfirmation(Character character) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Backstory'),
        content: Text(
          'Are you sure you want to delete the backstory for ${character.name}?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton.tonal(
            onPressed: () {
              Navigator.pop(context);
              _deleteBackstory(character.id);
            },
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }

  Widget _buildUpdateButton(AppState appState) {
    final isGenerating = appState.characterJourneyState['isGenerating'] as bool;
    return FloatingActionButton.extended(
      onPressed: isGenerating ? null : _updateCharacterInformation,
      icon: isGenerating
          ? const SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
              ),
            )
          : const Icon(Icons.update),
      label: Text(isGenerating ? 'Updating...' : 'Update All'),
    );
  }
}
