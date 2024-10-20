import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';
import 'universe_screen.dart';

class UniverseListScreen extends StatefulWidget {
  @override
  _UniverseListScreenState createState() => _UniverseListScreenState();
}

class _UniverseListScreenState extends State<UniverseListScreen> {
  List<dynamic> _universes = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _fetchUniverses();
  }

  Future<void> _fetchUniverses() async {
    setState(() {
      _isLoading = true;
    });
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/universes'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 200) {
        setState(() {
          _universes = json.decode(utf8.decode(response.bodyBytes));
          _isLoading = false;
        });
      } else {
        throw Exception('Failed to load universes');
      }
    } catch (error) {
      print('Error fetching universes: $error');
      Fluttertoast.showToast(
          msg: 'Error fetching universes: ${error.toString()}');
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _deleteUniverse(String universeId) async {
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/universes/$universeId'),
        headers: await getAuthHeaders(),
      );

      if (response.statusCode == 200) {
        Fluttertoast.showToast(msg: 'Universe deleted successfully');
        _fetchUniverses(); // Refresh the list
      } else {
        throw Exception('Failed to delete universe');
      }
    } catch (error) {
      print('Error deleting universe: $error');
      Fluttertoast.showToast(
          msg: 'Error deleting universe: ${error.toString()}');
    }
  }

  @override
  Widget build(BuildContext context) {
    return _isLoading
        ? Center(child: CircularProgressIndicator())
        : ListView.builder(
            itemCount: _universes.length,
            itemBuilder: (context, index) {
              final universe = _universes[index];
              return Dismissible(
                key: Key(universe['id']),
                background: Container(
                  color: Colors.red,
                  alignment: Alignment.centerRight,
                  padding: EdgeInsets.symmetric(horizontal: 20),
                  child: Icon(Icons.delete, color: Colors.white),
                ),
                direction: DismissDirection.endToStart,
                confirmDismiss: (direction) async {
                  return await showDialog(
                    context: context,
                    builder: (BuildContext context) {
                      return AlertDialog(
                        title: Text("Confirm"),
                        content: Text(
                            "Are you sure you want to delete this universe?"),
                        actions: <Widget>[
                          TextButton(
                            onPressed: () => Navigator.of(context).pop(false),
                            child: Text("CANCEL"),
                          ),
                          TextButton(
                            onPressed: () => Navigator.of(context).pop(true),
                            child: Text("DELETE"),
                          ),
                        ],
                      );
                    },
                  );
                },
                onDismissed: (direction) {
                  _deleteUniverse(universe['id']);
                },
                child: ListTile(
                  title: Text(universe['name']),
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) =>
                            UniverseScreen(universeId: universe['id']),
                      ),
                    );
                  },
                ),
              );
            },
          );
  }
}
