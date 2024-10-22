// In frontend/lib/models/relationship.dart
class Relationship {
  final String id;
  final String? characterId;
  final String? characterName;
  final String? relatedCharacterId;
  final String? relatedCharacterName;
  final String? relationshipType;

  Relationship({
    required this.id,
    this.characterId,
    this.characterName,
    this.relatedCharacterId,
    this.relatedCharacterName,
    this.relationshipType,
  });

  factory Relationship.fromJson(Map<String, dynamic> json) {
    return Relationship(
      id: json['id'],
      characterId: json['character_id'],
      characterName: json['character_name'],
      relatedCharacterId: json['related_character_id'],
      relatedCharacterName: json['related_character_name'],
      relationshipType: json['relationship_type'],
    );
  }
}
