import 'package:flutter/material.dart';
import 'package:expandable/expandable.dart';
import '../models/relationship.dart';
import '../widgets/edit_relationship_dialog.dart';

class CharacterRelationshipCard extends StatelessWidget {
  final String characterId;
  final String characterName;
  final List<Relationship> relationships;
  final Function(String) onDeleteRelationship;
  final Function(Relationship) onEditRelationship;

  const CharacterRelationshipCard({
    Key? key,
    required this.characterId,
    required this.characterName,
    required this.relationships,
    required this.onDeleteRelationship,
    required this.onEditRelationship,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final characterRelationships = relationships
        .where((relationship) =>
            relationship.character1_id == characterId ||
            relationship.character2_id == characterId)
        .toList();

    if (characterRelationships.isEmpty) {
      return SizedBox.shrink();
    }

    return Card(
      margin: EdgeInsets.all(8),
      child: ExpandablePanel(
        header: ListTile(
          title: Text(
            characterName,
            style: Theme.of(context).textTheme.titleLarge,
          ),
        ),
        collapsed: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16.0),
          child: Text(
            '${characterRelationships.length} relationship(s)',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ),
        expanded: Column(
          children: characterRelationships.map((relationship) {
            final otherCharacterName =
                relationship.getOtherCharacterName(characterId);
            return ListTile(
              title: Row(
                children: [
                  Expanded(
                    child: Text('With: $otherCharacterName'),
                  ),
                  Text(
                    relationship.relationshipType,
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                ],
              ),
              subtitle: Text(relationship.description),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    icon: Icon(Icons.edit),
                    onPressed: () {
                      showDialog(
                        context: context,
                        builder: (BuildContext context) {
                          return EditRelationshipDialog(
                            relationship: relationship,
                            onEditRelationship: onEditRelationship,
                          );
                        },
                      );
                    },
                  ),
                  IconButton(
                    icon: Icon(Icons.delete),
                    onPressed: () => onDeleteRelationship(relationship.id),
                  ),
                ],
              ),
            );
          }).toList(),
        ),
      ),
    );
  }
}
