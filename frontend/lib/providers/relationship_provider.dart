import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/constants.dart';

import '../models/relationship.dart';

class RelationshipProvider extends ChangeNotifier {
  bool _isLoading = false;
  String? _error;
  String? _message;
  final Map<String, dynamic> _graphData = {};
  List<Relationship> _relationships = [];

  bool get isLoading => _isLoading;
  String? get error => _error;
  String? get message => _message;
  Map<String, dynamic> get graphData => _graphData;
  List<Relationship> get relationships => _relationships;

  Future<void> analyzeRelationships(
      List<String> characterIds, String projectId) async {
    try {
      final response = await http.post(
        Uri.parse('$apiUrl/projects/$projectId/relationships/analyze'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: json
            .encode(characterIds), // Send the character IDs in the request body
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (data['alreadyAnalyzed'] == true) {
          _message = data['message'];
        } else {
          await getRelationships(
              projectId); // Refresh relationships after analysis
        }
        notifyListeners();
      } else {
        throw Exception('Failed to analyze relationships');
      }
    } catch (e) {
      _error = e.toString();
      notifyListeners();
      rethrow;
    }
  }

  Future<void> createRelationship({
    required String character1Id,
    required String relatedCharacterId,
    required String relationshipType,
    required String projectId,
    String? description,
  }) async {
    try {
      final headers = {};
      headers['Content-Type'] = 'application/json';
      final response = await http.post(
        Uri.parse('$apiUrl/projects/$projectId/relationships/'),
        body: json.encode({
          'character_id': character1Id,
          'related_character_id': relatedCharacterId,
          'relationship_type': relationshipType,
          if (description != null) 'description': description,
        }),
      );

      if (response.statusCode != 200) {
        throw Exception('Failed to create relationship');
      }

      // Refresh relationships after creating
      await getRelationships(projectId);
    } catch (e) {
      rethrow;
    }
  }

  Future<void> getRelationships(String projectId) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await http.get(
        Uri.parse('$apiUrl/projects/$projectId/relationships/'),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (data['relationships'] == null) {
          _relationships = [];
        } else {
          _relationships = (data['relationships'] as List)
              .map((json) {
                try {
                  return Relationship.fromJson(json);
                } catch (e) {
                  return null;
                }
              })
              .where((relationship) => relationship != null)
              .cast<Relationship>()
              .toList();
        }
      } else {
        final errorBody = json.decode(response.body);
        throw Exception(errorBody['detail'] ?? 'Failed to load relationships');
      }
    } catch (e) {
      _error = 'An error occurred: $e';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> updateRelationship(
      String relationshipId, String relationshipType, String projectId) async {
    try {
      final headers = {};
      headers['Content-Type'] = 'application/json';
      final response = await http.put(
        Uri.parse('$apiUrl/projects/$projectId/relationships/$relationshipId'),
        body: json.encode({
          'relationship_type': relationshipType,
        }),
      );

      if (response.statusCode == 200) {
        await getRelationships(projectId); // Refresh the relationships list
      } else {
        throw Exception('Failed to update relationship');
      }
    } catch (e) {
      _error = 'An error occurred: $e';
      notifyListeners();
    }
  }

  Future<void> deleteRelationship(
      String relationshipId, String projectId) async {
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/projects/$projectId/relationships/$relationshipId'),
      );

      if (response.statusCode == 200) {
        await getRelationships(projectId); // Refresh the relationships list
      } else {
        throw Exception('Failed to delete relationship');
      }
    } catch (e) {
      _error = 'An error occurred: $e';
      notifyListeners();
    }
  }
}
