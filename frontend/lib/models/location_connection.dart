import 'dart:convert';

class LocationConnection {
  final String id;
  final String location1Id;
  final String location2Id;
  final String location1Name; // For displaying location names
  final String location2Name; // For displaying location names
  final String? travelRoute; // Optional travel route between locations
  final String? culturalExchange; // Optional cultural exchange details
  final DateTime createdAt;
  final DateTime updatedAt;

  LocationConnection({
    required this.id,
    required this.location1Id,
    required this.location2Id,
    required this.location1Name,
    required this.location2Name,
    this.travelRoute,
    this.culturalExchange,
    required this.createdAt,
    required this.updatedAt,
  });

  factory LocationConnection.fromJson(Map<String, dynamic> json) {
    String processField(dynamic field) {
      if (field == null) return '';
      if (field is List) return field.join(' ');
      if (field is Map) return jsonEncode(field);
      return field.toString();
    }

    try {
      return LocationConnection(
        id: json['id']?.toString() ?? '',
        location1Id: json['location1_id']?.toString() ?? '',
        location2Id: json['location2_id']?.toString() ?? '',
        location1Name: json['location1_name']?.toString() ?? '',
        location2Name: json['location2_name']?.toString() ?? '',
        travelRoute: json['travel_route']?.toString(),
        culturalExchange: json['cultural_exchange']?.toString(),
        createdAt: DateTime.parse(
            json['created_at'] ?? DateTime.now().toIso8601String()),
        updatedAt: DateTime.parse(
            json['updated_at'] ?? DateTime.now().toIso8601String()),
      );
    } catch (e) {
      print('Error parsing LocationConnection: $e'); // For debugging
      rethrow;
    }
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'location1_id': location1Id,
      'location2_id': location2Id,
      'location1_name': location1Name,
      'location2_name': location2Name,
      'travel_route': travelRoute,
      'cultural_exchange': culturalExchange,
    };
  }
}
