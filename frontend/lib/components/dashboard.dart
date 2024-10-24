import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import 'dart:math';
import 'package:flutter/services.dart';

class Dashboard extends StatefulWidget {
  final String projectId;
  final Function(int, int, int) onProgressChanged;

  const Dashboard(
      {Key? key, required this.projectId, required this.onProgressChanged})
      : super(key: key);

  @override
  State<Dashboard> createState() => _DashboardState();
}

class _DashboardState extends State<Dashboard> {
  bool _isLoading = true;
  String _error = '';
  int _wordCount = 0;
  final TextEditingController _targetWordCountController =
      TextEditingController();

  @override
  void initState() {
    super.initState();
    _fetchData();
  }

  // Remove didChangeDependencies as it's causing extra refreshes
  // @override
  // void didChangeDependencies() {
  //   super.didChangeDependencies();
  //   Provider.of<AppState>(context, listen: false).refreshProjectData();
  // }

  Future<void> _fetchData() async {
    // Avoid fetching if widget is disposed
    if (!mounted) return;

    setState(() {
      _isLoading = true;
      _error = '';
    });

    try {
      // Only fetch progress data once
      await Provider.of<AppState>(context, listen: false)
          .fetchProgressData(widget.projectId);

      final headers = await getAuthHeaders();
      final chapterResponse = await http.get(
        Uri.parse('$apiUrl/chapters?project_id=${widget.projectId}'),
        headers: headers,
      );
      final codexResponse = await http.get(
        Uri.parse('$apiUrl/codex-items?project_id=${widget.projectId}'),
        headers: headers,
      );

      // Check if widget is still mounted before updating state
      if (!mounted) return;

      if (chapterResponse.statusCode == 200 &&
          codexResponse.statusCode == 200) {
        final chapterJsonResponse =
            json.decode(utf8.decode(chapterResponse.bodyBytes));
        final codexJsonResponse =
            json.decode(utf8.decode(codexResponse.bodyBytes));

        if (mounted) {
          Provider.of<AppState>(context, listen: false)
              .setChapters(chapterJsonResponse['chapters']);
          Provider.of<AppState>(context, listen: false)
              .setCodexItems(codexJsonResponse['codex_items']);

          _wordCount = 0;
          for (var chapter in chapterJsonResponse['chapters']) {
            _wordCount += chapter['content'].split(' ').length as int;
          }

          widget.onProgressChanged(chapterJsonResponse['chapters'].length,
              codexJsonResponse['codex_items'].length, _wordCount);

          setState(() {
            _isLoading = false;
          });
        }
      } else {
        if (mounted) {
          setState(() {
            _error = 'Error fetching data';
            _isLoading = false;
          });
        }
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = 'Error fetching data: $error';
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _showTargetWordCountDialog() async {
    _targetWordCountController.text =
        Provider.of<AppState>(context, listen: false)
            .targetWordCount
            .toString();
    return showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('Set Target Word Count'),
          content: TextFormField(
            controller: _targetWordCountController,
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            decoration: const InputDecoration(
              labelText: 'Target Word Count',
              border: OutlineInputBorder(),
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () async {
                final targetWordCount =
                    int.tryParse(_targetWordCountController.text) ?? 0;
                await Provider.of<AppState>(context, listen: false)
                    .updateTargetWordCount(targetWordCount);
                Navigator.pop(context);
              },
              child: const Text('Save'),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final appState = Provider.of<AppState>(context);

    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error.isNotEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(_error, style: const TextStyle(color: Colors.red)),
            ElevatedButton(
              onPressed: _fetchData,
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Story Progress',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 24),
            Row(
              children: [
                Expanded(
                  child: _buildProgressCard(
                    'Chapters',
                    appState.chapters.length,
                    Icons.book,
                    Colors.blue,
                    () => Navigator.pushNamed(context, '/chapters',
                            arguments: widget.projectId)
                        .then((_) {
                      _fetchData();
                    }),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: _buildProgressCard(
                    'Codex Entries',
                    appState.codexItems.length,
                    Icons.list_alt,
                    Colors.green,
                    () => Navigator.pushNamed(context, '/codex',
                            arguments: widget.projectId)
                        .then((_) {
                      _fetchData();
                    }),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),
            _buildWordCountCard(appState),
          ],
        ),
      ),
    );
  }

  Widget _buildProgressCard(
      String title, int value, IconData icon, Color color, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      child: Card(
        elevation: 4,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: color, size: 32),
              const SizedBox(height: 8),
              Text(
                title,
                style:
                    const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
              ),
              const SizedBox(height: 8),
              Text(
                value.toString(),
                style: TextStyle(
                    fontSize: 24, color: color, fontWeight: FontWeight.bold),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildWordCountCard(AppState appState) {
    double progress = appState.targetWordCount > 0
        ? min(_wordCount / appState.targetWordCount, 1.0)
        : 1.0;
    Color progressColor = Color.lerp(Colors.red, Colors.green, progress)!;

    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Word Count',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
                IconButton(
                  icon: const Icon(Icons.edit),
                  onPressed: _showTargetWordCountDialog,
                  tooltip: 'Set Target Word Count',
                ),
              ],
            ),
            const SizedBox(height: 16),
            LinearProgressIndicator(
              value: progress,
              valueColor: AlwaysStoppedAnimation<Color>(progressColor),
              backgroundColor: Colors.grey[300],
              minHeight: 10,
            ),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  '$_wordCount words',
                  style: const TextStyle(
                      fontSize: 18, fontWeight: FontWeight.bold),
                ),
                Text(
                  'Target: ${appState.targetWordCount}',
                  style: const TextStyle(fontSize: 16),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
