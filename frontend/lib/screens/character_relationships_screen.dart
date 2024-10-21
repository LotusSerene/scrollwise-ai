import 'package:flutter/material.dart';
import 'package:flutter_graph/flutter_graph.dart';
import 'package:provider/provider.dart';
import '../providers/relationship_provider.dart';
import '../widgets/relationship_tree.dart';
import '../providers/app_state.dart';
import '../models/relationship.dart';

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
  final Map<String, String> _selectedCharacters = {};

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<RelationshipProvider>(context, listen: false)
          .getRelationships(widget.projectId);
    });
  }

  Map<String, dynamic> _generateGraphData(List<Relationship> relationships) {
    Set<String> characters = {};
    List<Map<String, dynamic>> edges = [];

    for (var relationship in relationships) {
      if (relationship.characterId != null &&
          relationship.relatedCharacterId != null) {
        characters.add(relationship.characterId!);
        characters.add(relationship.relatedCharacterId!);
        edges.add({
          'from': relationship.characterId,
          'to': relationship.relatedCharacterId,
          'label': relationship.relationshipType ?? 'Unknown',
        });
      }
    }

    return {
      'nodes': characters.map((id) => {'id': id, 'label': id}).toList(),
      'edges': edges,
    };
  }

  @override
  Widget build(BuildContext context) {
    final relationshipProvider = Provider.of<RelationshipProvider>(context);
    final appState = Provider.of<AppState>(context);

    // Generate graph data if it's not available but we have relationships
    Map<String, dynamic> graphData = relationshipProvider.graphData.isNotEmpty
        ? relationshipProvider.graphData
        : _generateGraphData(relationshipProvider.relationships);

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(8.0),
          child: Wrap(
            spacing: 8.0,
            children: appState.codexItems
                .where((item) => item['type'] == 'character')
                .map((character) => FilterChip(
                      label: Text(character['name']),
                      selected: _selectedCharacters.containsKey(character['id']),
                      onSelected: (selected) {
                        setState(() {
                          if (selected) {
                            _selectedCharacters[character['id']] = character['name'];
                          } else {
                            _selectedCharacters.remove(character['id']);
                          }
                        });
                      },
                    ))
                .toList(),
          ),
        ),
        ElevatedButton(
          onPressed: _selectedCharacters.length >= 2
              ? () async {
                  // ... existing code ...
                }
              : null,
          child: const Text('Analyze Relationships'),
        ),
        Expanded(
          child: CustomScrollView(
            slivers: [
              SliverToBoxAdapter(
                child: FutureBuilder(
                  future: _initializeGraphData(),
                  builder: (context, snapshot) {
                    if (snapshot.connectionState == ConnectionState.waiting) {
                      return const Center(child: CircularProgressIndicator());
                    } else if (snapshot.hasError) {
                      return Center(child: Text('Error: ${snapshot.error}'));
                    } else if (snapshot.hasData) {
                      final graphData = snapshot.data!;
                      return graphData['nodes'].isNotEmpty
                          ? RelationshipTree(graphData: graphData)
                          : const Center(child: Text('Unable to generate graph'));
                    } else {
                      return const Center(child: Text('No relationships found'));
                    }
                  },
                ),
              ),
              SliverList(
                delegate: SliverChildBuilderDelegate(
                  (context, index) {
                    final relationship = relationshipProvider.relationships[index];
                    return ListTile(
                      title: Text(
                          '${relationship.characterName ?? 'Unknown'} - ${relationship.relatedCharacterName ?? 'Unknown'}'),
                      subtitle: Text(relationship.relationshipType ?? 'Unknown'),
                      trailing: IconButton(
                        icon: Icon(Icons.delete),
                        onPressed: () {
                          relationshipProvider.deleteRelationship(
                              relationship.id, widget.projectId);
                        },
                      ),
                      onTap: () {
                        _showEditRelationshipDialog(context, relationship);
                      },
                    );
                  },
                  childCount: relationshipProvider.relationships.length,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  void _showEditRelationshipDialog(
      BuildContext context, Relationship relationship) {
    final TextEditingController controller =
        TextEditingController(text: relationship.relationshipType ?? '');
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text('Edit Relationship'),
          content: TextField(
            controller: controller,
            decoration: InputDecoration(labelText: 'Relationship Type'),
          ),
          actions: <Widget>[
            TextButton(
              child: Text('Cancel'),
              onPressed: () {
                Navigator.of(context).pop();
              },
            ),
            TextButton(
              child: Text('Save'),
              onPressed: () {
                Provider.of<RelationshipProvider>(context, listen: false)
                    .updateRelationship(
                        relationship.id, controller.text, widget.projectId);
                Navigator.of(context).pop();
              },
            ),
          ],
        );
      },
    );
  }
}
