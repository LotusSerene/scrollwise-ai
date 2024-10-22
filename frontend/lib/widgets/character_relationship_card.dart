import 'package:flutter/material.dart';
import '../models/relationship.dart';

class CharacterRelationshipCard extends StatelessWidget {
  final String characterName;
  final List<Relationship> relationships;
  final Function(String) onDeleteRelationship;
  final Function(Relationship) onEditRelationship;

  const CharacterRelationshipCard({
    Key? key,
    required this.characterName,
    required this.relationships,
    required this.onDeleteRelationship,
    required this.onEditRelationship,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.all(8),
      child: ExpansionTile(
        title:
            Text(characterName, style: TextStyle(fontWeight: FontWeight.bold)),
        children: relationships.map((relationship) {
          final isCharacter1 = relationship.characterId == characterName;
          final otherCharacterName = isCharacter1
              ? relationship.relatedCharacterName
              : relationship.characterName;

          return ListTile(
            title: Text('$otherCharacterName'),
            subtitle: Text(relationship.relationshipType ?? 'Unknown'),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  icon: Icon(Icons.edit),
                  onPressed: () => onEditRelationship(relationship),
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
    );
  }
}
