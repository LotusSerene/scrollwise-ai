import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:logging/logging.dart';

final _logger = Logger('Validity');

class Validity extends StatefulWidget {
  final String projectId;

  const Validity({Key? key, required this.projectId}) : super(key: key);

  @override
  State<Validity> createState() => _ValidityState();
}

class _ValidityState extends State<Validity> {
  List<dynamic> _validityChecks = [];
  List<dynamic> _displayedChecks = [];
  bool _isLoading = true;
  bool _isLoadingMore = false;
  String? _error;
  dynamic _selectedCheck;
  bool _mounted = true;
  final ScrollController _scrollController = ScrollController();
  final int _itemsPerPage = 10;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _fetchValidityChecks();
  }

  @override
  void dispose() {
    _mounted = false;
    _scrollController.dispose();
    super.dispose();
  }

  void _safeSetState(VoidCallback fn) {
    if (_mounted && mounted) {
      setState(fn);
    }
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent * 0.8) {
      _loadMoreChecks();
    }
  }

  void _loadMoreChecks() {
    if (_isLoadingMore) return;

    final startIndex = _displayedChecks.length;
    if (startIndex >= _validityChecks.length) return;

    _safeSetState(() {
      _isLoadingMore = true;
    });

    Future.delayed(const Duration(milliseconds: 500), () {
      if (!_mounted) return;

      final newItems =
          _validityChecks.skip(startIndex).take(_itemsPerPage).toList();

      _safeSetState(() {
        _displayedChecks.addAll(newItems);
        _isLoadingMore = false;
      });
    });
  }

  Future<void> _fetchValidityChecks() async {
    _safeSetState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await http.get(
        Uri.parse('$apiUrl/validity-checks?project_id=${widget.projectId}'),
        headers: await getAuthHeaders(),
      );

      if (!_mounted) return;

      if (response.statusCode == 200) {
        final checks =
            json.decode(utf8.decode(response.bodyBytes))['validityChecks'];
        _safeSetState(() {
          _validityChecks = checks;
          _displayedChecks = checks.take(_itemsPerPage).toList();
          _isLoading = false;
        });
      } else {
        _safeSetState(() {
          _isLoading = false;
          _error = 'Failed to fetch validity checks';
        });
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Error fetching validity checks')));
      }
    } catch (error) {
      if (!mounted) return;
      _safeSetState(() {
        _isLoading = false;
        _error = error.toString();
      });
      _logger.severe('Error fetching validity checks: $error');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Error fetching validity checks')));
    }
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
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('Validity check deleted successfully')));
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Error deleting validity check')));
      }
    } catch (error) {
      _logger.severe('Error deleting validity check: $error');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Error deleting validity check')));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return _buildErrorState();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
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
                'Showing ${_displayedChecks.length} of ${_validityChecks.length} checks',
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
    return Container(
      color: Theme.of(context).colorScheme.surface,
      child: Scrollbar(
        controller: _scrollController,
        child: ListView.builder(
          padding: const EdgeInsets.all(16),
          controller: _scrollController,
          itemCount: _displayedChecks.length + (_isLoadingMore ? 1 : 0),
          itemBuilder: (context, index) {
            if (index == _displayedChecks.length) {
              return _buildLoadingIndicator();
            }

            final check = _displayedChecks[index];
            final isValid = check['isValid'] as bool;

            return Card(
              elevation: 1,
              margin: const EdgeInsets.only(bottom: 8),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: BorderSide(
                  color: Theme.of(context).colorScheme.outline.withOpacity(0.2),
                ),
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
        ),
      ),
    );
  }

  Widget _buildScoreIndicator(dynamic check) {
    final overallScore = (check['overallScore'] is int)
        ? (check['overallScore'] as int).toDouble()
        : (check['overallScore'] as double?) ?? 0.0;

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
    double convertScore(dynamic score) {
      if (score == null) return 0.0;
      return score is int ? score.toDouble() : (score as double);
    }

    showDialog(
      context: context,
      builder: (BuildContext context) {
        final overallScore = convertScore(check['overallScore']);
        final styleGuideScore = convertScore(check['styleGuideAdherenceScore']);
        final continuityScore = convertScore(check['continuityScore']);

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
                    '${(overallScore * 10).toStringAsFixed(1)}%'),
                _buildDetailItem('Style Guide Score',
                    '${(styleGuideScore * 10).toStringAsFixed(1)}%'),
                _buildDetailItem('Continuity Score',
                    '${(continuityScore * 10).toStringAsFixed(1)}%'),
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

  Widget _buildLoadingIndicator() {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16),
      alignment: Alignment.center,
      child: const CircularProgressIndicator(),
    );
  }
}
