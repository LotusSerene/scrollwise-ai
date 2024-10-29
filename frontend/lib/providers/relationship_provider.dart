import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/constants.dart';
import '../utils/auth.dart';
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
      final headers = await getAuthHeaders();
      final response = await http.post(
        Uri.parse('$apiUrl/relationships/analyze?project_id=$projectId'),
        headers: {
          ...headers,
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

  Future<void> createRelationship(String characterId, String relatedCharacterId,
      String relationshipType, String projectId,
      {String? description} // Add description parameter
      ) async {
    try {
      final headers = await getAuthHeaders();
      headers['Content-Type'] = 'application/json';
      final response = await http.post(
        Uri.parse('$apiUrl/relationships'),
        headers: headers,
        body: json.encode({
          'character_id': characterId,
          'related_character_id': relatedCharacterId,
          'relationship_type': relationshipType,
          'project_id': projectId,
          'description': description, // Include description in request
        }),
      );

      if (response.statusCode == 200) {
        await getRelationships(projectId);
      } else {
        throw Exception('Failed to create relationship');
      }
    } catch (e) {
      _error = 'An error occurred: $e';
      notifyListeners();
    }
  }

  Future<void> getRelationships(String projectId) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final headers = await getAuthHeaders();

      final response = await http.get(
        Uri.parse('$apiUrl/relationships?project_id=$projectId'),
        headers: headers,
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
                  print('Error parsing relationship: $e');
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
      print('Error in getRelationships: $e');
      _error = 'An error occurred: $e';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> updateRelationship(
      String relationshipId, String relationshipType, String projectId) async {
    try {
      final headers = await getAuthHeaders();
      headers['Content-Type'] = 'application/json';
      final response = await http.put(
        Uri.parse(
            '$apiUrl/relationships/$relationshipId?project_id=$projectId'),
        headers: headers,
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
      final headers = await getAuthHeaders();
      final response = await http.delete(
        Uri.parse(
            '$apiUrl/relationships/$relationshipId?project_id=$projectId'),
        headers: headers,
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
