import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';

class Validity extends StatefulWidget {
  const Validity({Key? key}) : super(key: key);

  @override
  State<Validity> createState() => _ValidityState();
}

class _ValidityState extends State<Validity> {
  List<dynamic> _validityChecks = [];
  dynamic _selectedCheck;

  @override
  void initState() {
    super.initState();
    _fetchValidityChecks();
  }

  Future<void> _fetchValidityChecks() async {
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/validity-checks'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 200) {
        setState(() {
          _validityChecks = json.decode(response.body)['validityChecks'];
        });
      } else {
        Fluttertoast.showToast(msg: 'Error fetching validity checks');
      }
    } catch (error) {
      print('Error fetching validity checks: $error');
      Fluttertoast.showToast(msg: 'Error fetching validity checks');
    }
  }

  void _handleCheckClick(dynamic check) {
    setState(() {
      _selectedCheck = check;
    });
  }

  Future<void> _handleDeleteCheck(String checkId) async {
    try {
      final response = await http.delete(
        Uri.parse('$apiUrl/validity-checks/$checkId'),
        headers: await getAuthHeaders(),
      );
      final jsonResponse = json.decode(response.body);
      if (response.statusCode == 204 && !jsonResponse.containsKey('error')) {
        setState(() {
          _validityChecks.removeWhere((check) => check['id'] == checkId);
          if (_selectedCheck != null && _selectedCheck['id'] == checkId) {
            _selectedCheck = null;
          }
        });
        Fluttertoast.showToast(msg: 'Validity check deleted successfully');
      } else {
        final errorMessage = jsonResponse['error'] ?? 'Error deleting validity check';
        Fluttertoast.showToast(msg: errorMessage);
      }
    } catch (error) {
      print('Error deleting validity check: $error');
      Fluttertoast.showToast(msg: 'Error deleting validity check');
    }
  }

  String _formatBool(bool? value) => value == null
      ? 'N/A'
      : value
          ? 'Yes'
          : 'No';
  String _formatString(String? value) => value ?? 'N/A';

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      itemCount: _validityChecks.length,
      padding: const EdgeInsets.all(16),
      itemBuilder: (context, index) {
        final check = _validityChecks[index];
        return Card(
          elevation: 3,
          margin: const EdgeInsets.symmetric(vertical: 8),
          child: ListTile(
            title: Text(
              '${check['chapterTitle']}: ${check['isValid'] ? 'Valid' : 'Invalid'}',
              style: const TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 18,
              ),
            ),
            onTap: () => showDialog(
              context: context,
              builder: (BuildContext context) {
                return AlertDialog(
                  title: Text(check['chapterTitle']),
                  content: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Validity: ${check['isValid'] ? 'Valid' : 'Invalid'}'),
                        Text('Chapter ID: ${check['chapterId']}'),
                        Text('Feedback: ${_formatString(check['feedback'])}'),
                        Text('Review: ${_formatString(check['review'])}'),
                        Text('Style Guide Adherence: ${_formatBool(check['style_guide_adherence'])}'),
                        Text('Style Guide Feedback: ${_formatString(check['style_guide_feedback'])}'),
                        Text('Continuity: ${_formatBool(check['continuity'])}'),
                        Text('Continuity Feedback: ${_formatString(check['continuity_feedback'])}'),
                        Text('Test Results: ${_formatString(check['test_results'])}'),
                      ],
                    ),
                  ),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Close'),
                    ),
                  ],
                );
              },
            ),
            trailing: IconButton(
              icon: const Icon(Icons.delete),
              onPressed: () => _handleDeleteCheck(check['id']),
            ),
          ),
        );
      },
    );
  }
}
