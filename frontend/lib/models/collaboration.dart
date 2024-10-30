class Collaboration {
  final String id;
  final String projectId;
  final String ownerId;
  final String? collaboratorId;
  final String accessToken;
  final Map<String, bool> permissions;
  final String status;
  final DateTime createdAt;
  final DateTime? expiresAt;

  Collaboration({
    required this.id,
    required this.projectId,
    required this.ownerId,
    this.collaboratorId,
    required this.accessToken,
    required this.permissions,
    required this.status,
    required this.createdAt,
    this.expiresAt,
  });

  factory Collaboration.fromJson(Map<String, dynamic> json) {
    return Collaboration(
      id: json['id'],
      projectId: json['project_id'],
      ownerId: json['owner_id'],
      collaboratorId: json['collaborator_id'],
      accessToken: json['access_token'],
      permissions: Map<String, bool>.from(json['permissions']),
      status: json['status'],
      createdAt: DateTime.parse(json['created_at']),
      expiresAt: json['expires_at'] != null
          ? DateTime.parse(json['expires_at'])
          : null,
    );
  }

  bool get isActive => status == 'active';
  bool get isPending => status == 'pending';
  bool get isExpired =>
      expiresAt != null && expiresAt!.isBefore(DateTime.now());
}
