import 'dart:convert';

class Event {
  final String id;
  final String title;
  final String description;
  final DateTime date;
  final String? characterId;
  final String? locationId;
  final DateTime createdAt;
  final DateTime updatedAt;
  final String? impact;

  Event({
    required this.id,
    required this.title,
    required this.description,
    required this.date,
    this.characterId,
    this.locationId,
    required this.createdAt,
    required this.updatedAt,
    this.impact,
  });

  factory Event.fromJson(Map<String, dynamic> json) {
    return Event(
      id: json['id'],
      title: json['title'],
      description: utf8.decode(json['description'].toString().codeUnits),
      date: DateTime.parse(json['date']),
      characterId: json['character_id'],
      locationId: json['location_id'],
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
      impact: json['impact'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'description': description,
      'date': date.toIso8601String(),
      'character_id': characterId,
      'location_id': locationId,
      'impact': impact,
    };
  }

  Event copyWith({
    String? title,
    String? description,
    DateTime? date,
    String? characterId,
    String? locationId,
    String? impact,
  }) {
    return Event(
      id: id,
      title: title ?? this.title,
      description: description ?? this.description,
      date: date ?? this.date,
      characterId: characterId ?? this.characterId,
      locationId: locationId ?? this.locationId,
      createdAt: createdAt,
      updatedAt: DateTime.now().toUtc(),
      impact: impact ?? this.impact,
    );
  }
}
