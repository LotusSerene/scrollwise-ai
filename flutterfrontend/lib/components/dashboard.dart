import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';

class Dashboard extends StatefulWidget {
  const Dashboard({Key? key}) : super(key: key);

  @override
  State<Dashboard> createState() => _DashboardState();
}

class _DashboardState extends State<Dashboard> {
  List<dynamic> _chatHistory = [];
  final TextEditingController _queryController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  List<dynamic> _characters = [];
  dynamic _editingCharacter;
  final TextEditingController _newCharacterNameController =
      TextEditingController();
  final TextEditingController _newCharacterDescriptionController =
      TextEditingController();
  List<dynamic> _chapters = [];
  bool _isMounted = true; // Flag to track if the widget is mounted

  @override
  void initState() {
    super.initState();
    _fetchChatHistory();
    _fetchCharacters();
    _fetchChapters();
  }

  @override
  void dispose() {
    _isMounted = false; // Set the flag to false when the widget is disposed
    super.dispose();
  }

  Future<void> _fetchChatHistory() async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/chat-history'),
        headers: headers,
      );
      final jsonResponse = json.decode(response.body);
      if (response.statusCode == 200 && !jsonResponse.containsKey('error')) {
        if (_isMounted) {
          setState(() {
            _chatHistory = jsonResponse['chatHistory'];
          });
        }
      } else {
        final errorMessage = jsonResponse['error'] ?? 'Error fetching chat history';
        Fluttertoast.showToast(msg: errorMessage);
      }
    } catch (error) {
      print('Error fetching chat history: $error');
      Fluttertoast.showToast(msg: 'Error fetching chat history');
    }
  }

  Future<void> _fetchCharacters() async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/characters'),
        headers: headers,
      );
      final jsonResponse = json.decode(response.body);
      if (response.statusCode == 200 && !jsonResponse.containsKey('error')) {
        if (_isMounted) {
          setState(() {
            _characters = jsonResponse['characters'];
          });
        }
      } else {
        final errorMessage = jsonResponse['error'] ?? 'Error fetching characters';
        Fluttertoast.showToast(msg: errorMessage);
      }
    } catch (error) {
      print('Error fetching characters: $error');
      Fluttertoast.showToast(msg: 'Error fetching characters');
    }
  }

  Future<void> _fetchChapters() async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('$apiUrl/chapters'),
        headers: headers,
      );
      final jsonResponse = json.decode(response.body);
      if (response.statusCode == 200 && !jsonResponse.containsKey('error')) {
        if (_isMounted) {
          setState(() {
            _chapters = jsonResponse['chapters'];
          });
        }
      } else {
        final errorMessage = jsonResponse['error'] ?? 'Error fetching chapters';
        Fluttertoast.showToast(msg: errorMessage);
      }
    } catch (error) {
      print('Error fetching chapters: $error');
      Fluttertoast.showToast(msg: 'Error fetching chapters');
    }
  }

  Future<void> _handleQuerySubmit() async {
    final query = _queryController.text.trim();
    if (query.isEmpty) return;

    setState(() {
      _chatHistory.add({'role': 'user', 'content': query});
      _queryController.clear();
    });

    try {
      final headers = await getAuthHeaders();
      final response = await http.post(
        Uri.parse('$apiUrl/knowledge-base/query'),
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: json.encode({
          'query': query,
          'chatHistory': _chatHistory,
        }),
      );
      final jsonResponse = json.decode(response.body);
      if (response.statusCode == 200 && !jsonResponse.containsKey('error')) {
        final responseData = jsonResponse;
        if (_isMounted) {
          setState(() {
            _chatHistory.add({'role': 'ai', 'content': responseData['result']});
          });
        }
      } else {
        final errorMessage = jsonResponse['error'] ?? 'Error querying knowledge base';
        Fluttertoast.showToast(msg: errorMessage);
      }
    } catch (error) {
      print('Error querying knowledge base: $error');
      Fluttertoast.showToast(msg: 'Error querying knowledge base');
    }

    _scrollController.animateTo(
      _scrollController.position.maxScrollExtent,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeOut,
    );
  }

  Future<void> _resetChatHistory() async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.post(
        Uri.parse('$apiUrl/knowledge-base/reset-chat-history'),
        headers: headers,
      );
      final jsonResponse = json.decode(response.body);
      if (response.statusCode == 200 && !jsonResponse.containsKey('error')) {
        if (_isMounted) {
          setState(() {
            _chatHistory = [];
          });
        }
        Fluttertoast.showToast(msg: 'Chat history reset');
      } else {
        final errorMessage = jsonResponse['error'] ?? 'Error resetting chat history';
        Fluttertoast.showToast(msg: errorMessage);
      }
    } catch (error) {
      print('Error resetting chat history: $error');
      Fluttertoast.showToast(msg: 'Error resetting chat history');
    }
  }

  void _handleEditCharacter(dynamic character) {
    setState(() {
      _editingCharacter = character;
      _newCharacterNameController.text = character['name'];
      _newCharacterDescriptionController.text = character['description'];
    });
  }

  void _handleCancelEdit() {
    setState(() {
      _editingCharacter = null;
      _newCharacterNameController.clear();
      _newCharacterDescriptionController.clear();
    });
  }

  Future<void> _handleSaveCharacter(dynamic characterData) async {
    try {
      final headers = await getAuthHeaders();

      http.Response response;
      if (_editingCharacter != null) {
        response = await http.put(
          Uri.parse('$apiUrl/characters/${characterData['id']}'),
          headers: {...headers, 'Content-Type': 'application/json'},
          body: json.encode(characterData),
        );
      } else {
        response = await http.post(
          Uri.parse('$apiUrl/characters'),
          headers: {...headers, 'Content-Type': 'application/json'},
          body: json.encode(characterData),
        );
      }
      final jsonResponse = json.decode(response.body);
      if ((response.statusCode == 200 || response.statusCode == 201) && !jsonResponse.containsKey('error')) {
        Fluttertoast.showToast(msg: response.statusCode == 200 ? 'Character updated successfully' : 'Character created successfully');
        setState(() {
          _editingCharacter = null;
          _newCharacterNameController.clear();
          _newCharacterDescriptionController.clear();
        });
        _fetchCharacters();
      } else {
        final errorMessage = jsonResponse['error'] ?? 'Error saving character';
        Fluttertoast.showToast(msg: errorMessage);
      }
    } catch (error) {
      print('Error saving character: $error');
      Fluttertoast.showToast(msg: 'Error saving character');
    }
  }

  Future<void> _handleDeleteCharacter(String characterId) async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.delete(
        Uri.parse('$apiUrl/characters/$characterId'),
        headers: headers,
      );
      final jsonResponse = json.decode(response.body);
      if (response.statusCode == 204 && !jsonResponse.containsKey('error')) {
        setState(() {
          _characters.removeWhere((char) => char['id'] == characterId);
        });
        Fluttertoast.showToast(msg: 'Character deleted successfully');
      } else {
        final errorMessage = jsonResponse['error'] ?? 'Error deleting character';
        Fluttertoast.showToast(msg: errorMessage);
      }
    } catch (error) {
      print('Error deleting character: $error');
      Fluttertoast.showToast(msg: 'Error deleting character');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF212529), // Dark background color
        borderRadius: BorderRadius.circular(8),
        boxShadow: const [
          BoxShadow(
            color: Color(0x1A000000), // Shadow color with opacity
            blurRadius: 4,
            offset: Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          const Text(
            'Dashboard',
            style: TextStyle(
              color: Color(0xFF007bff), // Primary color for headings
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 20),
          Expanded(
            child: GridView.count(
              crossAxisCount: 3, // 3 columns
              crossAxisSpacing: 20,
              mainAxisSpacing: 20,
              children: [
                // Chat section
                _buildChatSection(),
                // Characters section
                _buildCharactersSection(),
                // Chapters section
                _buildChaptersSection(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChatSection() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF343a40),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          const Text(
            'Chat with AI',
            style: TextStyle(
              color: Color(0xFF007bff),
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 10),
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              itemCount: _chatHistory.length,
              itemBuilder: (context, index) {
                final message = _chatHistory[index];
                return Align(
                  alignment: message['role'] == 'user'
                      ? Alignment.centerRight
                      : Alignment.centerLeft,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        vertical: 8, horizontal: 12),
                    margin: const EdgeInsets.only(bottom: 8),
                    decoration: BoxDecoration(
                      color: message['role'] == 'user'
                          ? const Color(0xFF007bff)
                          : const Color(0xFF495057),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      message['content'],
                      style: const TextStyle(
                        color: Colors.white,
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _queryController,
                  decoration: const InputDecoration(
                    hintText: 'Type your message...',
                    hintStyle: TextStyle(color: Colors.white),
                    enabledBorder: OutlineInputBorder(
                      borderSide: BorderSide(color: Color(0xFFced4da)),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderSide: BorderSide(color: Color(0xFF007bff)),
                    ),
                  ),
                  style: const TextStyle(color: Colors.white),
                  onSubmitted: (_) => _handleQuerySubmit(),
                ),
              ),
              IconButton(
                onPressed: _handleQuerySubmit,
                icon: const Icon(Icons.send, color: Colors.white),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ElevatedButton(
            onPressed: _resetChatHistory,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF007bff),
              padding:
                  const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              textStyle: const TextStyle(fontSize: 16),
            ),
            child: const Text('Reset Chat History'),
          ),
        ],
      ),
    );
  }

  Widget _buildCharactersSection() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF343a40),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          const Text(
            'Characters',
            style: TextStyle(
              color: Color(0xFF007bff),
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 10),
          Expanded(
            child: ListView.builder(
              itemCount: _characters.length,
              itemBuilder: (context, index) {
                final character = _characters[index];
                return ListTile(
                  title: Text(
                    character['name'],
                    style: const TextStyle(color: Colors.white),
                  ),
                  subtitle: Text(
                    character['description'],
                    style: const TextStyle(color: Colors.white70),
                  ),
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      IconButton(
                        onPressed: () => _handleEditCharacter(character),
                        icon: const Icon(Icons.edit, color: Colors.white),
                      ),
                      IconButton(
                        onPressed: () =>
                            _handleDeleteCharacter(character['id']),
                        icon: const Icon(Icons.delete, color: Colors.red),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 10),
          if (_editingCharacter != null)
            _buildEditCharacterSection()
          else
            _buildCreateCharacterSection(),
        ],
      ),
    );
  }

  Widget _buildEditCharacterSection() {
    return Column(
      children: [
        TextField(
          controller: _newCharacterNameController,
          decoration: const InputDecoration(
            labelText: 'Character Name',
            labelStyle: TextStyle(color: Colors.white),
            enabledBorder: OutlineInputBorder(
              borderSide: BorderSide(color: Color(0xFFced4da)),
            ),
            focusedBorder: OutlineInputBorder(
              borderSide: BorderSide(color: Color(0xFF007bff)),
            ),
          ),
          style: const TextStyle(color: Colors.white),
        ),
        const SizedBox(height: 10),
        TextField(
          controller: _newCharacterDescriptionController,
          decoration: const InputDecoration(
            labelText: 'Character Description',
            labelStyle: TextStyle(color: Colors.white),
            enabledBorder: OutlineInputBorder(
              borderSide: BorderSide(color: Color(0xFFced4da)),
            ),
            focusedBorder: OutlineInputBorder(
              borderSide: BorderSide(color: Color(0xFF007bff)),
            ),
          ),
          style: const TextStyle(color: Colors.white),
        ),
        const SizedBox(height: 10),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            ElevatedButton(
              onPressed: () => _handleSaveCharacter({
                'id': _editingCharacter != null
                    ? _editingCharacter['id']
                    : null,
                'name': _newCharacterNameController.text,
                'description': _newCharacterDescriptionController.text,
              }),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF007bff),
                padding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                textStyle: const TextStyle(fontSize: 16),
              ),
              child: const Text('Save'),
            ),
            ElevatedButton(
              onPressed: _handleCancelEdit,
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.grey,
                padding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                textStyle: const TextStyle(fontSize: 16),
              ),
              child: const Text('Cancel'),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildCreateCharacterSection() {
    return Column(
      children: [
        TextField(
          controller: _newCharacterNameController,
          decoration: const InputDecoration(
            labelText: 'Character Name',
            labelStyle: TextStyle(color: Colors.white),
            enabledBorder: OutlineInputBorder(
              borderSide: BorderSide(color: Color(0xFFced4da)),
            ),
            focusedBorder: OutlineInputBorder(
              borderSide: BorderSide(color: Color(0xFF007bff)),
            ),
          ),
          style: const TextStyle(color: Colors.white),
        ),
        const SizedBox(height: 10),
        TextField(
          controller: _newCharacterDescriptionController,
          decoration: const InputDecoration(
            labelText: 'Character Description',
            labelStyle: TextStyle(color: Colors.white),
            enabledBorder: OutlineInputBorder(
              borderSide: BorderSide(color: Color(0xFFced4da)),
            ),
            focusedBorder: OutlineInputBorder(
              borderSide: BorderSide(color: Color(0xFF007bff)),
            ),
          ),
          style: const TextStyle(color: Colors.white),
        ),
        const SizedBox(height: 10),
        ElevatedButton(
          onPressed: () => _handleSaveCharacter({
            'name': _newCharacterNameController.text,
            'description': _newCharacterDescriptionController.text,
          }),
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF007bff),
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
            textStyle: const TextStyle(fontSize: 16),
          ),
          child: const Text('Create Character'),
        ),
      ],
    );
  }

  Widget _buildChaptersSection() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF343a40),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          const Text(
            'Recent Chapters',
            style: TextStyle(
              color: Color(0xFF007bff),
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 10),
          Expanded(
            child: ListView.builder(
              itemCount: _chapters.length,
              itemBuilder: (context, index) {
                final chapter = _chapters[index];
                return ListTile(
                  title: Text(
                    chapter['title'],
                    style: const TextStyle(color: Colors.white),
                  ),
                  subtitle: Text(
                    chapter['content'].substring(0, 100) + '...',
                    style: const TextStyle(color: Colors.white70),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
