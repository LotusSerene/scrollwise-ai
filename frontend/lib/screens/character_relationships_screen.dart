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
import 'package:logging/logging.dart';

final _logger = Logger('Relationships');

class CharacterRelationshipsScreen extends StatefulWidget {
  final String projectId;

  const CharacterRelationshipsScreen({Key? key, required this.projectId})
      : super(key: key);

  @override
  State<CharacterRelationshipsScreen> createState() =>
      _CharacterRelationshipsScreenState();
}

class _CharacterRelationshipsScreenState
    extends State<CharacterRelationshipsScreen> {
  List<Map<String, dynamic>> characters = [];
  Set<String> selectedCharacters = {};

  @override
  void initState() {
    super.initState();

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
        Uri.parse('$apiUrl/projects/${widget.projectId}/codex/characters?project_id=${widget.projectId}'),
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
      _logger.severe('Error fetching characters: $e');
      if (!mounted) return;
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
              character1Id: character1Id,
              relatedCharacterId: character2Id,
              relationshipType: relationshipType,
              projectId: widget.projectId,
            );
          },
        );
      },
    );
  }

  void _analyzeRelationships() {
    final appState = Provider.of<AppState>(context, listen: false);
    final selectedCharacters = Set<String>.from(
        appState.characterRelationshipsState['selectedCharacters'] ?? {});

    if (selectedCharacters.length < 2) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select at least two characters')),
      );
      return;
    }

    // Update state before starting analysis
    appState.updateCharacterRelationshipsProgress(
      isGenerating: true,
      lastAnalyzedCharacters: List<String>.from(selectedCharacters),
    );

    Provider.of<RelationshipProvider>(context, listen: false)
        .analyzeRelationships(selectedCharacters.toList(), widget.projectId)
        .then((_) {
      // Update state after analysis is complete
      appState.updateCharacterRelationshipsProgress(
        isGenerating: false,
      );

      if (!mounted) return;
      final relationshipProvider =
          Provider.of<RelationshipProvider>(context, listen: false);
      if (relationshipProvider.message != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(relationshipProvider.message!)),
        );
      }
    }).catchError((error) {
      // Handle errors and update state
      appState.updateCharacterRelationshipsProgress(
        isGenerating: false,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error analyzing relationships: $error')),
      );
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
    return Consumer<AppState>(
      builder: (context, appState, child) {
        final isGenerating =
            appState.characterRelationshipsState['isGenerating'] as bool;

        return Scaffold(
          body: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildHeader(isGenerating),
                const SizedBox(height: 24),
                _buildCharacterSelection(),
                const SizedBox(height: 24),
                _buildRelationshipsList(),
              ],
            ),
          ),
          floatingActionButton: FloatingActionButton.extended(
            onPressed: isGenerating
                ? null
                : () => _showCreateRelationshipDialog(context),
            icon: const Icon(Icons.add),
            label: const Text('New Relationship'),
          ),
        );
      },
    );
  }

  Widget _buildHeader(bool isGenerating) {
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
          onPressed: isGenerating ? null : _analyzeRelationships,
          icon: isGenerating
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.psychology),
          label: Text(isGenerating ? 'Analyzing...' : 'Analyze'),
          style: ElevatedButton.styleFrom(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          ),
        ),
      ],
    );
  }

  Widget _buildCharacterSelection() {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        final selectedCharacters = appState
            .characterRelationshipsState['selectedCharacters'] as Set<String>;
        final isGenerating =
            appState.characterRelationshipsState['isGenerating'] as bool;

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
                    final isSelected =
                        selectedCharacters.contains(character['id']);
                    return FilterChip(
                      selected: isSelected,
                      label: Text(character['name'] ?? ''),
                      onSelected: isGenerating
                          ? null
                          : (bool value) {
                              final newSelection =
                                  Set<String>.from(selectedCharacters);
                              if (value) {
                                newSelection.add(character['id'] ?? '');
                              } else {
                                newSelection.remove(character['id'] ?? '');
                              }
                              appState.updateCharacterRelationshipsProgress(
                                selectedCharacters: newSelection,
                              );
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
      },
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
