import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/relationship_provider.dart';
import '../models/relationship.dart';
import '../widgets/create_relationship_dialog.dart';
import '../widgets/character_relationship_card.dart';

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
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<RelationshipProvider>(context, listen: false)
          .getRelationships(widget.projectId);
    });
  }

  void _showCreateRelationshipDialog(
      BuildContext context, List<Map<String, String>> characters) {
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Character Relationships'),
      ),
      body: Consumer<RelationshipProvider>(
        builder: (context, relationshipProvider, child) {
          if (relationshipProvider.isLoading) {
            return Center(child: CircularProgressIndicator());
          }

          if (relationshipProvider.error != null) {
            return Center(child: Text('Error: ${relationshipProvider.error}'));
          }

          final relationships = relationshipProvider.relationships;
          final Map<String, List<Relationship>> groupedRelationships = {};

          for (var relationship in relationships) {
            if (relationship.characterName != null) {
              groupedRelationships.putIfAbsent(
                  relationship.characterName!, () => []);
              groupedRelationships[relationship.characterName!]!
                  .add(relationship);
            }
          }

          return ListView(
            children: groupedRelationships.entries.map((entry) {
              return CharacterRelationshipCard(
                characterName: entry.key,
                relationships: entry.value,
                onDeleteRelationship: (relationshipId) {
                  relationshipProvider.deleteRelationship(
                      relationshipId, widget.projectId);
                },
                onEditRelationship: (relationship) {
                  // TODO: Implement edit relationship functionality
                },
              );
            }).toList(),
          );
        },
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          // TODO: Fetch characters from the API and pass them to the dialog
          _showCreateRelationshipDialog(context, []);
        },
        child: Icon(Icons.add),
      ),
    );
  }
}
