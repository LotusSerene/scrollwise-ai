import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:fluttertoast/fluttertoast.dart';

class Validity extends StatefulWidget {
  final String projectId;

  const Validity({Key? key, required this.projectId}) : super(key: key);

  @override
  State<Validity> createState() => _ValidityState();
}

class _ValidityState extends State<Validity> {
  List<dynamic> _validityChecks = [];
  bool _isLoading = true;
  String? _error;
  dynamic _selectedCheck; // Add this line

  @override
  void initState() {
    super.initState();
    _fetchValidityChecks();
  }

  Future<void> _fetchValidityChecks() async {
    try {
      final response = await http.get(
        Uri.parse('$apiUrl/validity-checks?project_id=${widget.projectId}'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 200) {
        setState(() {
          _validityChecks =
              json.decode(utf8.decode(response.bodyBytes))['validityChecks'];
          _isLoading = false;
        });
      } else {
        setState(() {
          _isLoading = false;
          _error = 'Failed to fetch validity checks';
        });
        Fluttertoast.showToast(msg: 'Error fetching validity checks');
      }
    } catch (error) {
      setState(() {
        _isLoading = false;
        _error = error.toString();
      });
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
        Uri.parse(
            '$apiUrl/validity-checks/$checkId?project_id=${widget.projectId}'),
        headers: await getAuthHeaders(),
      );
      if (response.statusCode == 200) {
        setState(() {
          _validityChecks.removeWhere((check) => check['id'] == checkId);
          if (_selectedCheck != null && _selectedCheck['id'] == checkId) {
            _selectedCheck = null;
          }
        });
        Fluttertoast.showToast(msg: 'Validity check deleted successfully');
      } else {
        final errorMessage = json.decode(response.body)['detail'] ??
            'Error deleting validity check';
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
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return _buildErrorState();
    }

    return Column(
      children: [
        _buildHeader(),
        Expanded(
          child: _validityChecks.isEmpty
              ? _buildEmptyState()
              : _buildValidityList(),
        ),
      ],
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Icon(
            Icons.check_circle,
            color: Theme.of(context).colorScheme.primary,
            size: 28,
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Validity Checks',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              Text(
                '${_validityChecks.length} checks performed',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context)
                          .colorScheme
                          .onSurface
                          .withOpacity(0.6),
                    ),
              ),
            ],
          ),
          const Spacer(),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchValidityChecks,
            tooltip: 'Refresh checks',
          ),
        ],
      ),
    );
  }

  Widget _buildValidityList() {
    return ListView.builder(
      itemCount: _validityChecks.length,
      padding: const EdgeInsets.all(16),
      itemBuilder: (context, index) {
        final check = _validityChecks[index];
        final isValid = check['isValid'] as bool;

        return Card(
          elevation: 2,
          margin: const EdgeInsets.only(bottom: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          child: InkWell(
            onTap: () => _showValidityDetails(check),
            borderRadius: BorderRadius.circular(12),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        isValid ? Icons.check_circle : Icons.error,
                        color: isValid
                            ? Theme.of(context).colorScheme.primary
                            : Theme.of(context).colorScheme.error,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          check['chapterTitle'],
                          style: Theme.of(context).textTheme.titleMedium,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.delete),
                        onPressed: () => _showDeleteDialog(check['id']),
                        tooltip: 'Delete check',
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  _buildScoreIndicator(check),
                  const SizedBox(height: 12),
                  Text(
                    check['generalFeedback'] ?? 'No feedback available',
                    style: Theme.of(context).textTheme.bodyMedium,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildScoreIndicator(dynamic check) {
    final overallScore = check['overallScore'] as double? ?? 0.0;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Overall Score',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            Text(
              '${(overallScore * 10).toStringAsFixed(1)}%',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        LinearProgressIndicator(
          value: overallScore / 10, // Add division by 10 here
          backgroundColor:
              Theme.of(context).colorScheme.surfaceContainerHighest,
          valueColor: AlwaysStoppedAnimation<Color>(
            Color.lerp(
              Theme.of(context).colorScheme.error,
              Theme.of(context).colorScheme.primary,
              overallScore / 10, // Also divide the color lerp value by 10
            )!,
          ),
          borderRadius: BorderRadius.circular(4),
          minHeight: 8,
        ),
      ],
    );
  }

  void _showValidityDetails(dynamic check) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Row(
            children: [
              Icon(
                check['isValid'] ? Icons.check_circle : Icons.error,
                color: check['isValid']
                    ? Theme.of(context).colorScheme.primary
                    : Theme.of(context).colorScheme.error,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  check['chapterTitle'],
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          content: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildDetailItem('Overall Score',
                    '${((check['overallScore'] ?? 0.0) * 10).toStringAsFixed(1)}%'),
                _buildDetailItem('Style Guide Score',
                    '${((check['styleGuideAdherenceScore'] ?? 0.0) * 10).toStringAsFixed(1)}%'),
                _buildDetailItem('Continuity Score',
                    '${((check['continuityScore'] ?? 0.0) * 10).toStringAsFixed(1)}%'),
                const Divider(),
                _buildDetailItem('General Feedback',
                    check['generalFeedback'] ?? 'No feedback available'),
                _buildDetailItem(
                    'Style Guide Feedback',
                    check['styleGuideAdherenceExplanation'] ??
                        'No feedback available'),
                _buildDetailItem('Continuity Feedback',
                    check['continuityExplanation'] ?? 'No feedback available'),
                if (check['areasForImprovement'] != null)
                  _buildDetailItem('Areas for Improvement',
                      check['areasForImprovement'].toString()),
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
    );
  }

  Widget _buildDetailItem(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ],
      ),
    );
  }

  void _showDeleteDialog(String checkId) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Row(
            children: [
              Icon(Icons.warning, color: Theme.of(context).colorScheme.error),
              const SizedBox(width: 8),
              const Text('Delete Check'),
            ],
          ),
          content: const Text(
            'Are you sure you want to delete this validity check? This action cannot be undone.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton.icon(
              icon: const Icon(Icons.delete),
              label: const Text('Delete'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Theme.of(context).colorScheme.error,
              ),
              onPressed: () {
                Navigator.pop(context);
                _handleDeleteCheck(checkId);
              },
            ),
          ],
        );
      },
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.fact_check,
            size: 64,
            color: Theme.of(context).colorScheme.secondary.withOpacity(0.5),
          ),
          const SizedBox(height: 16),
          Text(
            'No Validity Checks',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: Theme.of(context).colorScheme.secondary,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            'Run validity checks on your chapters to see results here',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color:
                      Theme.of(context).colorScheme.onSurface.withOpacity(0.6),
                ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.error_outline,
            size: 64,
            color: Theme.of(context).colorScheme.error,
          ),
          const SizedBox(height: 16),
          Text(
            _error!,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: Theme.of(context).colorScheme.error,
                ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _fetchValidityChecks,
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
          ),
        ],
      ),
    );
  }
}
