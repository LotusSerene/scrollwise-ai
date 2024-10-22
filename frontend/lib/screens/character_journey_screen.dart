import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import '../utils/auth.dart';
import '../models/character.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/constants.dart';
import '../widgets/character_detail_dialog.dart'; // Make sure to create this file

class CharacterJourneyScreen extends StatefulWidget {
  final String projectId;

  const CharacterJourneyScreen({Key? key, required this.projectId})
      : super(key: key);

  @override
  _CharacterJourneyScreenState createState() => _CharacterJourneyScreenState();
}

class _CharacterJourneyScreenState extends State<CharacterJourneyScreen> {
  List<Character> characters = [];
  Set<String> ignoredCharacters = {};
  bool isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadCharacters();
  }

  Future<void> _loadCharacters() async {
    setState(() => isLoading = true);
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/codex/characters?project_id=${widget.projectId}'),
        headers: headers,
      );
      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body)['characters'];
        setState(() {
          characters = data.map((json) => Character.fromJson(json)).toList();
        });
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error loading characters: $e')),
      );
    } finally {
      setState(() => isLoading = false);
    }
  }

  Future<void> _updateCharacterInformation() async {
    setState(() => isLoading = true);
    try {
      final headers = await getAuthHeaders();
      headers['Content-Type'] = 'application/json';

      bool anyUpdates = false;

      for (var character in characters) {
        if (!ignoredCharacters.contains(character.id)) {
          final response = await http.post(
            Uri.parse(
                '$apiUrl/codex/characters/${character.id}/extract-backstory?project_id=${widget.projectId}'),
            headers: headers,
            body: json.encode({
              'character_id': character.id,
              'chapter_id': 'latest',
            }),
          );

          if (response.statusCode == 200) {
            final responseBody = json.decode(response.body);
            if (responseBody != null && responseBody['backstory'] != null) {
              setState(() {
                final index =
                    characters.indexWhere((c) => c.id == character.id);
                if (index != -1) {
                  characters[index] = characters[index].copyWith(
                    backstory: responseBody['backstory']['new_backstory'],
                  );
                }
              });
              anyUpdates = true;
            } else if (responseBody != null &&
                responseBody['message'] != null) {
              print(
                  'Message for character ${character.id}: ${responseBody['message']}');
            }
          } else {
            print('Error updating character ${character.id}: ${response.body}');
          }
        }
      }

      if (anyUpdates) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Character information updated')),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text(
                  'No new information found or no unprocessed chapters available')),
        );
      }
    } catch (e) {
      print('Error updating character information: $e');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error updating character information: $e')),
      );
    } finally {
      setState(() => isLoading = false);
    }
  }

  void _showCharacterDetails(Character character) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return CharacterDetailDialog(character: character);
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : ListView.builder(
              itemCount: characters.length + 1,
              itemBuilder: (context, index) {
                if (index == characters.length) {
                  return Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: ElevatedButton(
                      onPressed: _updateCharacterInformation,
                      child: const Text('Update Information'),
                    ),
                  );
                }
                final character = characters[index];
                return Opacity(
                  opacity: ignoredCharacters.contains(character.id) ? 0.5 : 1.0,
                  child: Card(
                    margin: const EdgeInsets.all(8.0),
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(character.name,
                              style: Theme.of(context).textTheme.titleLarge),
                          const SizedBox(height: 8),
                          Text(character.description),
                          const SizedBox(height: 16),
                          Text('Backstory:',
                              style: Theme.of(context).textTheme.titleMedium),
                          Text(character.backstory ?? 'No backstory available'),
                          const SizedBox(height: 16),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              ElevatedButton(
                                onPressed: () =>
                                    _showCharacterDetails(character),
                                child: const Text('View Details'),
                              ),
                              Switch(
                                value:
                                    !ignoredCharacters.contains(character.id),
                                onChanged: (value) {
                                  setState(() {
                                    if (value) {
                                      ignoredCharacters.remove(character.id);
                                    } else {
                                      ignoredCharacters.add(character.id);
                                    }
                                  });
                                },
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
    );
  }
}
