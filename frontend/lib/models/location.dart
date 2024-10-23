class Location {
  final String id;
  final String name;
  final String description;
  final String? coordinates;
  final DateTime createdAt;
  final DateTime updatedAt;
  final String? significance;

  Location({
    required this.id,
    required this.name,
    required this.description,
    this.coordinates,
    required this.createdAt,
    required this.updatedAt,
    this.significance,
  });

  factory Location.fromJson(Map<String, dynamic> json) {
    return Location(
      id: json['id'],
      name: json['name'],
      description: json['description'],
      coordinates: json['coordinates'],
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
      significance: json['significance'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'description': description,
      'coordinates': coordinates,
      'significance': significance,
    };
  }

  Location copyWith({
    String? name,
    String? description,
    String? coordinates,
    String? significance,
  }) {
    return Location(
      id: id,
      name: name ?? this.name,
      description: description ?? this.description,
      coordinates: coordinates ?? this.coordinates,
      createdAt: createdAt,
      updatedAt: DateTime.now().toUtc(),
      significance: significance ?? this.significance,
    );
  }
}
