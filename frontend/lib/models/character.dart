import 'dart:convert';

class Character {
  final String id;
  final String name;
  final String description;
  final String backstory;
  final DateTime createdAt;
  final DateTime updatedAt;

  Character({
    required this.id,
    required this.name,
    required this.description,
    required this.backstory,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Character.fromJson(Map<String, dynamic> json) {
    return Character(
      id: json['id'],
      name: json['name'],
      description: utf8.decode(json['description'].toString().codeUnits),
      backstory: json['backstory'] ?? '',
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }

  Character copyWith({
    String? id,
    String? name,
    String? description,
    String? backstory,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Character(
      id: id ?? this.id,
      name: name ?? this.name,
      description: description ?? this.description,
      backstory: backstory ?? this.backstory,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}
