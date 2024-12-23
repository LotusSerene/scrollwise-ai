import 'dart:convert';

class Relationship {
  final String id;
  final String character1Id;
  final String character2Id;
  final String character1Name;
  final String character2Name;
  final String relationshipType;
  final String description;

  const Relationship({
    required this.id,
    required this.character1Id,
    required this.character2Id,
    required this.character1Name,
    required this.character2Name,
    required this.relationshipType,
    required this.description,
  });

  factory Relationship.fromJson(Map<String, dynamic> json) {
    return Relationship(
      id: json['id'] as String? ?? '',
      character1Id: json['character1_id'] as String? ?? '',
      character2Id: json['character2_id'] as String? ?? '',
      character1Name: json['character1_name'] as String? ?? '',
      character2Name: json['character2_name'] as String? ?? '',
      relationshipType: json['relationship_type'] as String? ?? '',
      description: utf8.decode(json['description'].toString().codeUnits),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'character1_id': character1Id,
        'character2_id': character2Id,
        'relationship_type': relationshipType,
        'description': description,
      };

  // Add a method to get the display name if needed
  String getDisplayName(String characterId) {
    return character1Id == characterId ? character2Id : character1Id;
  }

  // Add a method to get the other character's name
  String getOtherCharacterName(String characterId) {
    return character1Id == characterId ? character2Name : character1Name;
  }
}
