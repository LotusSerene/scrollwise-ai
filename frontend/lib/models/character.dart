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
      description: json['description'],
      backstory: json['backstory'] ?? '',
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }
}
