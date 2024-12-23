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
            relationship.character1Id == characterId ||
            relationship.character2Id == characterId)
        .toList();

    if (characterRelationships.isEmpty) {
      return const SizedBox.shrink();
    }

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      elevation: 2,
      child: ExpandablePanel(
        theme: ExpandableThemeData(
          headerAlignment: ExpandablePanelHeaderAlignment.center,
          iconColor: Theme.of(context).colorScheme.primary,
        ),
        header: ListTile(
          leading: CircleAvatar(
            backgroundColor: Theme.of(context)
                .colorScheme
                .surfaceContainerHighest, // More subtle background
            child: Icon(
              Icons.person,
              color: Theme.of(context)
                  .colorScheme
                  .onSurfaceVariant, // More subtle icon color
              size: 20, // Slightly smaller icon
            ),
          ),
          title: Text(
            characterName,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          subtitle: Text(
            '${characterRelationships.length} relationship(s)',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
        collapsed: const SizedBox.shrink(),
        expanded: Column(
          children: characterRelationships.map((relationship) {
            return _buildRelationshipTile(context, relationship);
          }).toList(),
        ),
      ),
    );
  }

  Widget _buildRelationshipTile(
      BuildContext context, Relationship relationship) {
    return Container(
      decoration: BoxDecoration(
        border: Border(
          top: BorderSide(
            color: Theme.of(context).dividerColor,
            width: 0.5,
          ),
        ),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 8,
        ),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.connect_without_contact,
                  size: 20,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    relationship.getOtherCharacterName(characterId),
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              relationship.relationshipType,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.primary,
                    fontWeight: FontWeight.bold,
                  ),
            ),
          ],
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text(relationship.description),
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              icon: Icon(
                Icons.edit,
                color: Theme.of(context).colorScheme.primary,
              ),
              onPressed: () => _showEditDialog(context, relationship),
            ),
            IconButton(
              icon: Icon(
                Icons.delete,
                color: Theme.of(context).colorScheme.error,
              ),
              onPressed: () => _showDeleteDialog(context, relationship),
            ),
          ],
        ),
      ),
    );
  }

  void _showEditDialog(BuildContext context, Relationship relationship) {
    showDialog(
      context: context,
      builder: (context) => EditRelationshipDialog(
        relationship: relationship,
        onEditRelationship: onEditRelationship,
      ),
    );
  }

  void _showDeleteDialog(BuildContext context, Relationship relationship) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Relationship'),
        content:
            const Text('Are you sure you want to delete this relationship?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              onDeleteRelationship(relationship.id);
              Navigator.pop(context);
            },
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }
}
