import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import '../utils/auth.dart';
import '../models/character.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/constants.dart';
import '../widgets/character_detail_dialog.dart'; // Make sure to create this file
import 'package:expandable/expandable.dart'; // Add this package to pubspec.yaml

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

  Future<void> _deleteBackstory(String characterId) async {
    setState(() => isLoading = true);
    try {
      final headers = await getAuthHeaders();
      final response = await http.delete(
        Uri.parse(
            '$apiUrl/codex-items/characters/$characterId/backstory?project_id=${widget.projectId}'),
        headers: headers,
      );
      if (response.statusCode == 200) {
        setState(() {
          final index = characters.indexWhere((c) => c.id == characterId);
          if (index != -1) {
            characters[index] = characters[index].copyWith(backstory: '');
          }
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Backstory deleted successfully')),
        );
      } else {
        throw Exception('Failed to delete backstory');
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error deleting backstory: $e')),
      );
    } finally {
      setState(() => isLoading = false);
    }
  }

  Future<void> _editBackstory(Character character) async {
    final TextEditingController _backstoryController =
        TextEditingController(text: character.backstory);

    final String? result = await showDialog<String>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text('Edit Backstory for ${character.name}'),
          content: TextField(
            controller: _backstoryController,
            maxLines: null,
            decoration: const InputDecoration(
              hintText: 'Enter backstory...',
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () =>
                  Navigator.pop(context, _backstoryController.text),
              child: const Text('Save'),
            ),
          ],
        );
      },
    );

    if (result != null) {
      setState(() => isLoading = true);
      try {
        final headers = await getAuthHeaders();
        headers['Content-Type'] = 'application/json';
        final response = await http.put(
          Uri.parse(
              '$apiUrl/codex-items/characters/${character.id}/backstory?project_id=${widget.projectId}'),
          headers: headers,
          body: json.encode(result), // Change this line
        );

        if (response.statusCode == 200) {
          setState(() {
            final index = characters.indexWhere((c) => c.id == character.id);
            if (index != -1) {
              characters[index] = characters[index].copyWith(backstory: result);
            }
          });
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Backstory updated successfully')),
          );
        } else {
          print('Error updating backstory: ${response.body}');
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
                content: Text('Error updating backstory: ${response.body}')),
          );
        }
      } catch (e) {
        print('Error updating backstory: $e');
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error updating backstory: $e')),
        );
      } finally {
        setState(() => isLoading = false);
      }
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
                    child: ExpandablePanel(
                      header: ListTile(
                        title: Text(character.name,
                            style: Theme.of(context).textTheme.titleLarge),
                        trailing: Switch(
                          value: !ignoredCharacters.contains(character.id),
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
                      ),
                      collapsed: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16.0),
                        child: Text(
                          character.description,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      expanded: Padding(
                        padding: const EdgeInsets.all(16.0),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Description:',
                                style: Theme.of(context).textTheme.titleMedium),
                            Text(character.description),
                            const SizedBox(height: 16),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text('Backstory:',
                                    style: Theme.of(context)
                                        .textTheme
                                        .titleMedium),
                                Row(
                                  children: [
                                    IconButton(
                                      icon: const Icon(Icons.edit),
                                      onPressed: () =>
                                          _editBackstory(character),
                                    ),
                                    IconButton(
                                      icon: const Icon(Icons.delete),
                                      onPressed: () =>
                                          _deleteBackstory(character.id),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                            Text(character.backstory.isNotEmpty
                                ? character.backstory
                                : 'No backstory available'),
                          ],
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
    );
  }
}
