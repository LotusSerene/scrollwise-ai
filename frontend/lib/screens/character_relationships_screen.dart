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

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<RelationshipProvider>(context, listen: false)
          .getRelationships(widget.projectId);
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
      // Handle error (e.g., show a snackbar)
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
        SnackBar(content: Text('Please select at least two characters')),
      );
      return;
    }

    // Debug print to check the data
    print('Selected characters before analysis: $selectedCharacters');

    // Convert Set to List and ensure all elements are strings
    List<String> characterIds = selectedCharacters.toList();

    // Debug print to check the converted list
    print('Character IDs for analysis: $characterIds');

    Provider.of<RelationshipProvider>(context, listen: false)
        .analyzeRelationships(characterIds, widget.projectId);
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
      body: Column(
        children: [
          ElevatedButton(
            onPressed: _analyzeRelationships,
            child: Text('Analyze Relationships'),
          ),
          Expanded(
            flex: 1,
            child: ListView(
              children: characters.map((character) {
                return CheckboxListTile(
                  title: Text(character['name'] ?? ''),
                  value: selectedCharacters.contains(character['id']),
                  onChanged: (bool? value) {
                    setState(() {
                      if (value == true) {
                        selectedCharacters.add(character['id'] ?? '');
                      } else {
                        selectedCharacters.remove(character['id'] ?? '');
                      }
                    });
                  },
                );
              }).toList(),
            ),
          ),
          Expanded(
            flex: 2,
            child: Consumer<RelationshipProvider>(
              builder: (context, relationshipProvider, child) {
                if (relationshipProvider.isLoading) {
                  return Center(child: CircularProgressIndicator());
                }

                if (relationshipProvider.error != null) {
                  return Center(
                      child: Text('Error: ${relationshipProvider.error}'));
                }

                final relationships = relationshipProvider.relationships;
                print(
                    'Building relationships list. Count: ${relationships.length}'); // Debug log

                return ListView.builder(
                  itemCount: characters.length,
                  itemBuilder: (context, index) {
                    final character = characters[index];
                    final characterRelationships = relationships
                        .where((r) =>
                            r.character1_id == character['id'] ||
                            r.character2_id == character['id'])
                        .toList();

                    print(
                        'Character ${character['name']} has ${characterRelationships.length} relationships'); // Debug log

                    return CharacterRelationshipCard(
                      characterId: character['id'] ?? '',
                      characterName: character['name'] ?? '',
                      relationships: characterRelationships,
                      onDeleteRelationship: (relationshipId) {
                        relationshipProvider.deleteRelationship(
                            relationshipId, widget.projectId);
                      },
                      onEditRelationship: _handleEditRelationship,
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showCreateRelationshipDialog(context),
        child: Icon(Icons.add),
      ),
    );
  }
}
