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
    return Container(
      padding: const EdgeInsets.all(20),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            flex: 1,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Validity Checks',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 10),
                Expanded(
                  child: ListView.builder(
                    itemCount: _validityChecks.length,
                    itemBuilder: (context, index) {
                      final check = _validityChecks[index];
                      return ListTile(
                        title: Text(
                          '${check['chapterTitle']}: ${check['isValid'] ? 'Valid' : 'Invalid'}',
                        ),
                        selected: _selectedCheck == check,
                        onTap: () => _handleCheckClick(check),
                        trailing: IconButton(
                          icon: const Icon(Icons.delete),
                          onPressed: () => _handleDeleteCheck(check['id']),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 20),
          Expanded(
            flex: 2,
            child: _selectedCheck != null
                ? Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _selectedCheck['chapterTitle'],
                        style: const TextStyle(
                            fontSize: 18, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 10),
                      Text(
                          'Validity: ${_selectedCheck['isValid'] ? 'Valid' : 'Invalid'}'),
                      Text('Chapter ID: ${_selectedCheck['chapterId']}'),
                      Text(
                          'Feedback: ${_formatString(_selectedCheck['feedback'])}'),
                      Text(
                          'Review: ${_formatString(_selectedCheck['review'])}'),
                      Text(
                          'Style Guide Adherence: ${_formatBool(_selectedCheck['style_guide_adherence'])}'),
                      Text(
                          'Style Guide Feedback: ${_formatString(_selectedCheck['style_guide_feedback'])}'),
                      Text(
                          'Continuity: ${_formatBool(_selectedCheck['continuity'])}'),
                      Text(
                          'Continuity Feedback: ${_formatString(_selectedCheck['continuity_feedback'])}'),
                      Text(
                          'Test Results: ${_formatString(_selectedCheck['test_results'])}'),
                    ],
                  )
                : const SizedBox(),
          ),
        ],
      ),
    );
  }
}
