import 'dart:convert';

class Relationship {
  final String id;
  final String character1_id;
  final String character2_id;
  final String character1_name;
  final String character2_name;
  final String relationshipType;
  final String description;

  const Relationship({
    required this.id,
    required this.character1_id,
    required this.character2_id,
    required this.character1_name,
    required this.character2_name,
    required this.relationshipType,
    required this.description,
  });

  factory Relationship.fromJson(Map<String, dynamic> json) {
    return Relationship(
      id: json['id'] as String? ?? '',
      character1_id: json['character1_id'] as String? ?? '',
      character2_id: json['character2_id'] as String? ?? '',
      character1_name: json['character1_name'] as String? ?? '',
      character2_name: json['character2_name'] as String? ?? '',
      relationshipType: json['relationship_type'] as String? ?? '',
      description: utf8.decode(json['description'].toString().codeUnits),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'character1_id': character1_id,
        'character2_id': character2_id,
        'relationship_type': relationshipType,
        'description': description,
      };

  // Add a method to get the display name if needed
  String getDisplayName(String characterId) {
    return character1_id == characterId ? character2_id : character1_id;
  }

  // Add a method to get the other character's name
  String getOtherCharacterName(String characterId) {
    return character1_id == characterId ? character2_name : character1_name;
  }
}
