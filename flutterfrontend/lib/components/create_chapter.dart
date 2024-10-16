import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:fluttertoast/fluttertoast.dart';
import '../utils/auth.dart';
import '../utils/constants.dart';

class CreateChapter extends StatefulWidget {
  const CreateChapter({Key? key}) : super(key: key);

  @override
  State<CreateChapter> createState() => _CreateChapterState();
}

class _CreateChapterState extends State<CreateChapter> {
  final _formKey = GlobalKey<FormState>();
  int _numChapters = 1;
  String _plot = '';
  String _writingStyle = '';
  String _styleGuide = '';
  int _minWordCount = 1000;
  String _additionalInstructions = '';
  bool _isGenerating = false;
  String _streamedContent = '';
  List<dynamic> _presets = [];
  bool _isLoadingPresets = true;
  String? _selectedPreset;
  String _newPresetName = '';

  @override
  void initState() {
    super.initState();
    _fetchPresets();
  }

  Future<void> _fetchPresets() async {
    setState(() {
      _isLoadingPresets = true;
    });
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/presets/'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 200) {
        setState(() {
          _presets = json.decode(response.body);
          _isLoadingPresets = false;
        });
      } else {
        throw Exception('Failed to load presets');
      }
    } catch (error) {
      print('Error fetching presets: $error');
      Fluttertoast.showToast(msg: 'Error fetching presets');
      setState(() {
        _isLoadingPresets = false;
      });
    }
  }

  Future<void> _handleSavePreset() async {
    try {
      final requestBody = {
        'name': _newPresetName,
        'data': {
          'numChapters': _numChapters,
          'plot': _plot,
          'writingStyle': _writingStyle,
          'styleGuide': _styleGuide,
          'minWordCount': _minWordCount,
          'additionalInstructions': _additionalInstructions,
        },
        'instructions': { // Added "instructions" field
          'styleGuide': _styleGuide,
          'minWordCount': _minWordCount,
          'additionalInstructions': _additionalInstructions,
        },
      };

      final response = await http.post(
        Uri.parse('$apiUrl/presets/'),
        headers: {
          ...await getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: json.encode(requestBody),
      );

      if (response.statusCode == 201) {
        setState(() {
          _presets.add(json.decode(response.body));
          _newPresetName = '';
        });
        Fluttertoast.showToast(msg: 'Preset saved successfully');
      } else {
        final errorData = json.decode(response.body);
        Fluttertoast.showToast(
            msg: 'Error saving preset: ${errorData['detail']}');
      }
    } catch (error) {
      print('Error saving preset: $error');
      Fluttertoast.showToast(msg: 'Error saving preset');
    }
  }

  Future<void> _handlePresetChange(String? presetName) async {
    if (presetName == null) {
      setState(() {
        _selectedPreset = null;
      });
      return;
    }

    try {
      final response = await http.get(
        Uri.parse('$apiUrl/presets/${Uri.encodeComponent(presetName)}'),
        headers: await getAuthHeaders(),
      );

      if (response.statusCode == 200) {
        final preset = json.decode(response.body);
        _handleLoadPreset(preset);
      } else {
        throw Exception('Failed to load preset');
      }
    } catch (error) {
      print('Error fetching preset: $error');
      Fluttertoast.showToast(msg: 'Error fetching preset');
      setState(() {
        _selectedPreset = null;
      });
    }
  }

  void _handleLoadPreset(Map<String, dynamic> preset) {
    setState(() {
      _selectedPreset = preset['name'];
      _numChapters = preset['data']['numChapters'] ?? 1;
      _plot = preset['data']['plot'] ?? '';
      _writingStyle = preset['data']['writingStyle'] ?? '';
      _styleGuide = preset['data']['styleGuide'] ?? '';
      _minWordCount = preset['data']['minWordCount'] ?? 1000;
      _additionalInstructions = preset['data']['additionalInstructions'] ?? '';
    });
    Fluttertoast.showToast(
        msg: 'Preset "${preset['name']}" loaded successfully');
  }

  Future<void> _handleDeletePreset(String presetName) async {
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/presets/${Uri.encodeComponent(presetName)}'),
        headers: await getAuthHeaders(),
      );

      if (response.statusCode == 204) {
        setState(() {
          _presets.removeWhere((p) => p['name'] == presetName);
          _selectedPreset = null; // Reset selected preset
        });
        Fluttertoast.showToast(msg: 'Preset deleted successfully');
      } else {
        final errorData = json.decode(response.body);
        Fluttertoast.showToast(
            msg: 'Error deleting preset: ${errorData['detail']}');
      }
    } catch (error) {
      print('Error deleting preset: $error');
      Fluttertoast.showToast(msg: 'Error deleting preset');
    }
  }

  Future<void> _handleSubmit(BuildContext context) async {
    if (_formKey.currentState!.validate()) {
      setState(() {
        _isGenerating = true;
        _streamedContent = '';
      });

      try {
        final headers = {
          ...await getAuthHeaders(),
          'Content-Type': 'application/json',
        };

        final requestBody = {
          'numChapters': _numChapters,
          'plot': _plot,
          'writingStyle': _writingStyle,
          'styleGuide': _styleGuide,
          'minWordCount': _minWordCount,
          'additionalInstructions': _additionalInstructions,
          'instructions': {
            'styleGuide': _styleGuide,
            'minWordCount': _minWordCount,
            'additionalInstructions': _additionalInstructions,
          },
        };

        final response = await http.post(
          Uri.parse('$apiUrl/chapters/generate'),
          headers: headers,
          body: json.encode(requestBody),
        );

        if (response.statusCode == 200) {
          // Handle the response, likely a stream of data
          response.body.split('\n').forEach((line) {
            if (line.trim().isNotEmpty) {
              final data = json.decode(line);
              if (data['type'] == 'chunk') {
                setState(() {
                  _streamedContent += data['content'];
                });
              } else if (data['type'] == 'final') {
                // Chapter generated
                Fluttertoast.showToast(msg: 'Chapter generated successfully');
              } else if (data['type'] == 'done') {
                // All chapters generated
                setState(() {
                  _isGenerating = false;
                });
                Fluttertoast.showToast(
                    msg: 'All chapters generated successfully');
              } else if (data['error'] != null) {
                setState(() {
                  _isGenerating = false;
                });
                Fluttertoast.showToast(msg: 'Error: ${data['error']}');
              }
            }
          });
        } else {
          setState(() {
            _isGenerating = false;
          });
          Fluttertoast.showToast(msg: 'Error generating chapters');
        }
      } catch (error) {
        print('Error generating chapters: $error');
        setState(() {
          _isGenerating = false;
        });
        Fluttertoast.showToast(msg: 'Error generating chapters');
      }
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
      child: SingleChildScrollView( // Wrap content in SingleChildScrollView
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Generate New Chapter',
              style: TextStyle(
                color: Color(0xFF007bff), // Primary color for headings
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 20),
            const Text(
              'Fill in the form below to generate a new chapter for your story. Provide as much detail as possible to get the best results.',
              style: TextStyle(
                color: Color(0xFFf8f9fa), // Light text color
                fontSize: 16,
              ),
            ),
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Presets:',
                        style: TextStyle(
                          color: Color(0xFFf8f9fa),
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 10),
                      _isLoadingPresets
                          ? const CircularProgressIndicator()
                          : DropdownButtonFormField<String>(
                              value: _selectedPreset,
                              onChanged: _handlePresetChange,
                              items: _presets.map((preset) {
                                return DropdownMenuItem<String>(
                                  value: preset['name'],
                                  child: Text(preset['name']),
                                );
                              }).toList(),
                              decoration: const InputDecoration(
                                enabledBorder: OutlineInputBorder(
                                  borderSide:
                                      BorderSide(color: Color(0xFFced4da)),
                                ),
                                focusedBorder: OutlineInputBorder(
                                  borderSide:
                                      BorderSide(color: Color(0xFF007bff)),
                                ),
                              ),
                            ),
                      if (_selectedPreset != null)
                        IconButton(
                          onPressed: () => _handleDeletePreset(_selectedPreset!),
                          icon: const Icon(Icons.delete, color: Colors.red),
                        ),
                    ],
                  ),
                ),
                const SizedBox(width: 20),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Save Preset:',
                        style: TextStyle(
                          color: Color(0xFFf8f9fa),
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextFormField(
                        decoration: const InputDecoration(
                          hintText: 'Preset name',
                          hintStyle: TextStyle(color: Color(0xFFf8f9fa)),
                          enabledBorder: OutlineInputBorder(
                            borderSide: BorderSide(color: Color(0xFFced4da)),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderSide: BorderSide(color: Color(0xFF007bff)),
                          ),
                        ),
                        style: const TextStyle(color: Color(0xFFf8f9fa)),
                        onChanged: (value) {
                          setState(() {
                            _newPresetName = value;
                          });
                        },
                      ),
                      const SizedBox(height: 10),
                      ElevatedButton(
                        onPressed:
                            _newPresetName.isNotEmpty ? _handleSavePreset : null,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF007bff),
                          padding: const EdgeInsets.symmetric(
                              horizontal: 20, vertical: 10),
                          textStyle: const TextStyle(fontSize: 16),
                        ),
                        child: const Text('Save'),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            Form(
              key: _formKey,
              child: Column(
                children: [
                  TextFormField(
                    decoration: const InputDecoration(
                      labelText: 'Number of Chapters',
                      labelStyle: TextStyle(color: Color(0xFFf8f9fa)),
                      enabledBorder: OutlineInputBorder(
                        borderSide: BorderSide(color: Color(0xFFced4da)),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderSide: BorderSide(color: Color(0xFF007bff)),
                      ),
                    ),
                    style: const TextStyle(color: Color(0xFFf8f9fa)),
                    keyboardType: TextInputType.number,
                    initialValue: _numChapters.toString(),
                    onChanged: (value) {
                      setState(() {
                        _numChapters = int.tryParse(value) ?? 1;
                      });
                    },
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return 'Please enter a number';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 15),
                  TextFormField(
                    decoration: const InputDecoration(
                      labelText: 'Plot',
                      labelStyle: TextStyle(color: Color(0xFFf8f9fa)),
                      enabledBorder: OutlineInputBorder(
                        borderSide: BorderSide(color: Color(0xFFced4da)),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderSide: BorderSide(color: Color(0xFF007bff)),
                      ),
                    ),
                    style: const TextStyle(color: Color(0xFFf8f9fa)),
                    maxLines: null,
                    initialValue: _plot,
                    onChanged: (value) {
                      setState(() {
                        _plot = value;
                      });
                    },
                  ),
                  const SizedBox(height: 15),
                  TextFormField(
                    decoration: const InputDecoration(
                      labelText: 'Writing Style',
                      labelStyle: TextStyle(color: Color(0xFFf8f9fa)),
                      enabledBorder: OutlineInputBorder(
                        borderSide: BorderSide(color: Color(0xFFced4da)),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderSide: BorderSide(color: Color(0xFF007bff)),
                      ),
                    ),
                    style: const TextStyle(color: Color(0xFFf8f9fa)),
                    initialValue: _writingStyle,
                    onChanged: (value) {
                      setState(() {
                        _writingStyle = value;
                      });
                    },
                  ),
                  const SizedBox(height: 15),
                  TextFormField(
                    decoration: const InputDecoration(
                      labelText: 'Style Guide',
                      labelStyle: TextStyle(color: Color(0xFFf8f9fa)),
                      enabledBorder: OutlineInputBorder(
                        borderSide: BorderSide(color: Color(0xFFced4da)),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderSide: BorderSide(color: Color(0xFF007bff)),
                      ),
                    ),
                    style: const TextStyle(color: Color(0xFFf8f9fa)),
                    maxLines: null,
                    initialValue: _styleGuide,
                    onChanged: (value) {
                      setState(() {
                        _styleGuide = value;
                      });
                    },
                  ),
                  const SizedBox(height: 15),
                  TextFormField(
                    decoration: const InputDecoration(
                      labelText: 'Minimum Word Count',
                      labelStyle: TextStyle(color: Color(0xFFf8f9fa)),
                      enabledBorder: OutlineInputBorder(
                        borderSide: BorderSide(color: Color(0xFFced4da)),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderSide: BorderSide(color: Color(0xFF007bff)),
                      ),
                    ),
                    style: const TextStyle(color: Color(0xFFf8f9fa)),
                    keyboardType: TextInputType.number,
                    initialValue: _minWordCount.toString(),
                    onChanged: (value) {
                      setState(() {
                        _minWordCount = int.tryParse(value) ?? 0;
                      });
                    },
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return 'Please enter a number';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 15),
                  TextFormField(
                    decoration: const InputDecoration(
                      labelText: 'Additional Instructions',
                      labelStyle: TextStyle(color: Color(0xFFf8f9fa)),
                      enabledBorder: OutlineInputBorder(
                        borderSide: BorderSide(color: Color(0xFFced4da)),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderSide: BorderSide(color: Color(0xFF007bff)),
                      ),
                    ),
                    style: const TextStyle(color: Color(0xFFf8f9fa)),
                    maxLines: null,
                    initialValue: _additionalInstructions,
                    onChanged: (value) {
                      setState(() {
                        _additionalInstructions = value;
                      });
                    },
                  ),
                  const SizedBox(height: 20),
                  ElevatedButton(
                    onPressed: () => _handleSubmit(context),
                    style: ElevatedButton.styleFrom(
                      backgroundColor:
                          const Color(0xFF007bff), // Primary color for button
                      padding: const EdgeInsets.symmetric(
                          horizontal: 20, vertical: 10),
                      textStyle: const TextStyle(fontSize: 18),
                    ),
                    child: _isGenerating
                        ? const CircularProgressIndicator(color: Colors.white)
                        : const Text('Generate Chapter'),
                  ),
                  const SizedBox(height: 20),
                  if (_streamedContent.isNotEmpty)
                    Expanded(
                      child: SingleChildScrollView(
                        child: Text(
                          _streamedContent,
                          style: const TextStyle(color: Color(0xFFf8f9fa)),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
