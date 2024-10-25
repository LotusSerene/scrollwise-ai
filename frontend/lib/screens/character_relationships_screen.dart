import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/relationship_provider.dart';
import '../models/relationship.dart';
import '../widgets/create_relationship_dialog.dart';
import '../widgets/character_relationship_card.dart';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../providers/app_state.dart';

class CharacterRelationshipsScreen extends StatefulWidget {
  final String projectId;

  const CharacterRelationshipsScreen({Key? key, required this.projectId})
      : super(key: key);

  @override
  _CharacterRelationshipsScreenState createState() =>
      _CharacterRelationshipsScreenState();
}

class _CharacterRelationshipsScreenState
    extends State<CharacterRelationshipsScreen> {
  List<Map<String, dynamic>> characters = [];
  Set<String> selectedCharacters = {};
  late AppState _appState;

  @override
  void initState() {
    super.initState();
    _appState = Provider.of<AppState>(context, listen: false);

    // Initialize with saved state if it exists
    final savedState = _appState.getGenerationState('character_relationships');
    if (savedState != null) {
      setState(() {
        selectedCharacters = Set<String>.from(
            savedState.lastGeneratedItem?['selectedCharacters'] ?? {});
      });
    }

    WidgetsBinding.instance.addPostFrameCallback((_) {
      final relationshipProvider =
          Provider.of<RelationshipProvider>(context, listen: false);
      relationshipProvider.getRelationships(widget.projectId);
      _fetchCharacters();
    });
  }

  Future<void> _fetchCharacters() async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/codex/characters?project_id=${widget.projectId}'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() {
          characters = (data['characters'] as List)
              .map((item) => {
                    'id': item['id'].toString(),
                    'name': item['name'].toString()
                  })
              .toList();
        });
      } else {
        throw Exception('Failed to load characters');
      }
    } catch (e) {
      print('Error fetching characters: $e');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error fetching characters: $e')),
      );
    }
  }

  void _showCreateRelationshipDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return CreateRelationshipDialog(
          characters: characters,
          onCreateRelationship: (character1Id, character2Id, relationshipType) {
            Provider.of<RelationshipProvider>(context, listen: false)
                .createRelationship(
              character1Id,
              character2Id,
              relationshipType,
              widget.projectId,
            );
          },
        );
      },
    );
  }

  void _analyzeRelationships() {
    if (selectedCharacters.length < 2) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select at least two characters')),
      );
      return;
    }

    _appState.setGenerationState(
      'character_relationships',
      isGenerating: true,
      lastGeneratedItem: {
        'selectedCharacters': List<String>.from(selectedCharacters)
      },
    );

    List<String> characterIds = selectedCharacters.toList();

    Provider.of<RelationshipProvider>(context, listen: false)
        .analyzeRelationships(characterIds, widget.projectId)
        .then((_) {
      _appState.setGenerationState(
        'character_relationships',
        isGenerating: false,
        lastGeneratedItem: {
          'selectedCharacters': List<String>.from(selectedCharacters),
        },
      );

      final relationshipProvider =
          Provider.of<RelationshipProvider>(context, listen: false);
      if (relationshipProvider.message != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(relationshipProvider.message!)),
        );
      }
    });
  }

  void _handleEditRelationship(Relationship relationship) {
    Provider.of<RelationshipProvider>(context, listen: false)
        .updateRelationship(
      relationship.id,
      relationship.relationshipType,
      widget.projectId,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildHeader(),
            const SizedBox(height: 24),
            _buildCharacterSelection(),
            const SizedBox(height: 24),
            _buildRelationshipsList(),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showCreateRelationshipDialog(context),
        icon: const Icon(Icons.add),
        label: const Text('New Relationship'),
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Character Relationships',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            Text(
              'Manage and analyze character connections',
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
          onPressed: _analyzeRelationships,
          icon: const Icon(Icons.psychology),
          label: const Text('Analyze'),
          style: ElevatedButton.styleFrom(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          ),
        ),
      ],
    );
  }

  Widget _buildCharacterSelection() {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.people,
                    color: Theme.of(context).colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Select Characters to Analyze',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ],
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: characters.map((character) {
                final isSelected = selectedCharacters.contains(character['id']);
                return FilterChip(
                  selected: isSelected,
                  label: Text(character['name'] ?? ''),
                  onSelected: (bool value) {
                    setState(() {
                      if (value) {
                        selectedCharacters.add(character['id'] ?? '');
                      } else {
                        selectedCharacters.remove(character['id'] ?? '');
                      }
                    });
                  },
                  avatar: Icon(
                    Icons.person,
                    size: 18,
                    color: isSelected
                        ? Theme.of(context).colorScheme.onPrimary
                        : Theme.of(context).colorScheme.primary,
                  ),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRelationshipsList() {
    return Expanded(
      child: Consumer<RelationshipProvider>(
        builder: (context, relationshipProvider, child) {
          if (relationshipProvider.isLoading) {
            return const Center(
              child: CircularProgressIndicator(),
            );
          }

          if (relationshipProvider.error != null) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    Icons.error_outline,
                    size: 48,
                    color: Theme.of(context).colorScheme.error,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Error: ${relationshipProvider.error}',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
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
              return CharacterRelationshipCard(
                characterId: character['id'] ?? '',
                characterName: character['name'] ?? '',
                relationships: relationshipProvider.relationships,
                onDeleteRelationship: (relationshipId) {
                  relationshipProvider.deleteRelationship(
                    relationshipId,
                    widget.projectId,
                  );
                },
                onEditRelationship: _handleEditRelationship,
              );
            },
          );
        },
      ),
    );
  }
}
