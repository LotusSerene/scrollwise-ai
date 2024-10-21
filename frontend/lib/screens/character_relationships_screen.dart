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

    return CustomScrollView(
      slivers: [
        SliverList(
          delegate: SliverChildBuilderDelegate(
            (context, index) {
              return relationshipProvider.isLoading
                  ? const Center(child: CircularProgressIndicator())
                  : relationshipProvider.relationships.isEmpty
                      ? const Center(child: Text('No relationships found'))
                      : graphData['nodes'].isNotEmpty
                          ? RelationshipTree(graphData: graphData)
                          : const Center(child: Text('Unable to generate graph'));
            },
            childCount: 1,
          ),
        ),
        SliverToBoxAdapter(
          child: ListView.builder(
            itemCount: relationshipProvider.relationships.length,
            itemBuilder: (context, index) {
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
