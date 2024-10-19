import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:typed_data';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';

class CodexGeneration extends StatefulWidget {
  final String projectId;

  const CodexGeneration({Key? key, required this.projectId}) : super(key: key);

  @override
  State<CodexGeneration> createState() => _CodexGenerationState();
}

class _CodexGenerationState extends State<CodexGeneration> {
  final _formKey = GlobalKey<FormState>();
  String _selectedType = 'worldbuilding';
  String? _selectedSubtype;
  String _description = '';
  bool _isGenerating = false;
  Map<String, dynamic>? _generatedItem;

  final List<String> _types = ['worldbuilding', 'character', 'item'];
  final Map<String, List<String>> _subtypes = {
    'worldbuilding': ['history', 'culture', 'geography'],
  };

  Future<void> _handleSubmit() async {
    if (_formKey.currentState!.validate()) {
      setState(() {
        _isGenerating = true;
      });

      try {
        final headers = {...await getAuthHeaders()};

        final requestBody = {
          'codex_type': _selectedType,
          'subtype': _selectedSubtype,
          'description': _description,
        };

        final response = await http.post(
          Uri.parse('$apiUrl/codex/generate?project_id=${widget.projectId}'),
          headers: headers,
          body: utf8.encode(json.encode(requestBody)),
        );

        if (response.statusCode == 200) {
          final data = json.decode(utf8.decode(response.bodyBytes));
          setState(() {
            _generatedItem = data['item'];
          });
          Fluttertoast.showToast(msg: 'Codex item generated successfully');
        } else {
          Fluttertoast.showToast(
              msg: 'Error generating codex item: ${response.body}');
        }
      } catch (error) {
        print('Error generating codex item: $error');
        Fluttertoast.showToast(msg: 'Error generating codex item: $error');
      } finally {
        setState(() {
          _isGenerating = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF212529),
        borderRadius: BorderRadius.circular(8),
        boxShadow: const [
          BoxShadow(
            color: Color(0x1A000000),
            blurRadius: 4,
            offset: Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Generate Codex Item',
            style: TextStyle(
              color: Color(0xFF007bff), // Primary color for headings
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 20),
          Form(
            key: _formKey,
            child: Column(
              children: [
                DropdownButtonFormField<String>(
                  value: _selectedType,
                  onChanged: (value) {
                    setState(() {
                      _selectedType = value!;
                      _selectedSubtype = null;
                    });
                  },
                  items: _types.map((type) {
                    return DropdownMenuItem<String>(
                      value: type,
                      child: Text(type.capitalize()),
                    );
                  }).toList(),
                  decoration: InputDecoration(
                    labelText: 'Type',
                    labelStyle: TextStyle(color: Color(0xFFf8f9fa)),
                    enabledBorder: OutlineInputBorder(
                      borderSide: BorderSide(color: Color(0xFFced4da)),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderSide: BorderSide(color: Color(0xFF007bff)),
                    ),
                  ),
                ),
                SizedBox(height: 10),
                if (_selectedType == 'worldbuilding')
                  DropdownButtonFormField<String>(
                    value: _selectedSubtype,
                    onChanged: (value) {
                      setState(() {
                        _selectedSubtype = value;
                      });
                    },
                    items: _subtypes[_selectedType]!.map((subtype) {
                      return DropdownMenuItem<String>(
                        value: subtype,
                        child: Text(subtype.capitalize()),
                      );
                    }).toList(),
                    decoration: InputDecoration(
                      labelText: 'Subtype',
                      labelStyle: TextStyle(color: Color(0xFFf8f9fa)),
                      enabledBorder: OutlineInputBorder(
                        borderSide: BorderSide(color: Color(0xFFced4da)),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderSide: BorderSide(color: Color(0xFF007bff)),
                      ),
                    ),
                  ),
                SizedBox(height: 10),
                TextFormField(
                  decoration: InputDecoration(
                    labelText: 'Description',
                    labelStyle: TextStyle(color: Color(0xFFf8f9fa)),
                    enabledBorder: OutlineInputBorder(
                      borderSide: BorderSide(color: Color(0xFFced4da)),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderSide: BorderSide(color: Color(0xFF007bff)),
                    ),
                  ),
                  style: TextStyle(color: Color(0xFFf8f9fa)),
                  maxLines: 3,
                  onChanged: (value) {
                    setState(() {
                      _description = value;
                    });
                  },
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return 'Please enter a description';
                    }
                    return null;
                  },
                ),
                SizedBox(height: 20),
                if (_isGenerating)
                  CircularProgressIndicator()
                else
                  ElevatedButton(
                    onPressed: _handleSubmit,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Color(0xFF007bff),
                      padding:
                          EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                      textStyle: TextStyle(fontSize: 16),
                    ),
                    child: Text('Generate'),
                  ),
                if (_generatedItem != null)
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SizedBox(height: 20),
                      Text(
                        'Generated Codex Item:',
                        style: TextStyle(
                          color: Color(0xFF007bff),
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      SizedBox(height: 10),
                      Text(
                        'Name: ${_generatedItem!['name']}',
                        style: TextStyle(color: Color(0xFFf8f9fa)),
                      ),
                      SizedBox(height: 5),
                      Text(
                        'Description: ${_generatedItem!['description']}',
                        style: TextStyle(color: Color(0xFFf8f9fa)),
                      ),
                    ],
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

extension StringExtension on String {
  String capitalize() {
    return "${this[0].toUpperCase()}${this.substring(1)}";
  }
}
