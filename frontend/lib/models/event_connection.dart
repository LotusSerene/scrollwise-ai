import 'dart:convert';

class EventConnection {
  final String id;
  final String event1Id;
  final String event2Id;
  final String event1Title; // Add this
  final String event2Title; // Add this
  final String connectionType;
  final String description;
  final String impact;
  final DateTime createdAt;
  final DateTime updatedAt;

  EventConnection({
    required this.id,
    required this.event1Id,
    required this.event2Id,
    required this.event1Title, // Add this
    required this.event2Title, // Add this
    required this.connectionType,
    required this.description,
    required this.impact,
    required this.createdAt,
    required this.updatedAt,
  });

  factory EventConnection.fromJson(Map<String, dynamic> json) {
    String processField(dynamic field) {
      if (field == null) return '';
      if (field is List) return field.join(' ');
      if (field is Map) return jsonEncode(field);
      return field.toString();
    }

    try {
      return EventConnection(
        id: json['id']?.toString() ?? '',
        event1Id: json['event1_id']?.toString() ?? '',
        event2Id: json['event2_id']?.toString() ?? '',
        event1Title: json['event1_title']?.toString() ?? '', // Add this
        event2Title: json['event2_title']?.toString() ?? '', // Add this
        connectionType: json['connection_type']?.toString() ?? '',
        description: processField(json['description']),
        impact: processField(json['impact']),
        createdAt: DateTime.parse(
            json['created_at'] ?? DateTime.now().toIso8601String()),
        updatedAt: DateTime.parse(
            json['updated_at'] ?? DateTime.now().toIso8601String()),
      );
    } catch (e) {
      print('Error parsing EventConnection: $e'); // For debugging
      rethrow;
    }
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'event1_id': event1Id,
      'event2_id': event2Id,
      'connection_type': connectionType,
      'description': description,
      'impact': impact,
    };
  }
}
