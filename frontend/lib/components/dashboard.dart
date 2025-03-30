import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/auth.dart';
import '../utils/constants.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import 'dart:math';
import 'package:flutter/services.dart';
import '../utils/text_utils.dart';

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

  Future<void> _fetchData() async {
    if (!mounted) return;

    final scaffoldMessenger = ScaffoldMessenger.of(context);
    final appState = Provider.of<AppState>(context, listen: false);

    setState(() {
      _isLoading = true;
      _error = '';
    });

    try {
      final headers = await getAuthHeaders();

      // Fetch chapters
      final chapterResponse = await http.get(
        Uri.parse('$apiUrl/chapters?project_id=${widget.projectId}'),
        headers: headers,
      );

      if (chapterResponse.statusCode == 200) {
        final chapterJsonResponse =
            json.decode(utf8.decode(chapterResponse.bodyBytes));
        appState.setChapters(chapterJsonResponse['chapters']);

        _wordCount = 0;
        for (var chapter in chapterJsonResponse['chapters']) {
          _wordCount += getWordCount(chapter['content']);
        }
      }

      // Fetch codex items
      final codexResponse = await http.get(
        Uri.parse('$apiUrl/codex-items?project_id=${widget.projectId}'),
        headers: headers,
      );

      if (codexResponse.statusCode == 200) {
        final codexJsonResponse =
            json.decode(utf8.decode(codexResponse.bodyBytes));
        appState.setCodexItems(codexJsonResponse['codex_items']);
      }

      if (!mounted) return;
      widget.onProgressChanged(
          appState.chapters.length, appState.codexItems.length, _wordCount);
      setState(() => _isLoading = false);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = 'Error fetching data: $error';
        _isLoading = false;
      });
      scaffoldMessenger.showSnackBar(
        SnackBar(content: Text('Error: $error')),
      );
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
                final navigator = Navigator.of(context);
                final targetWordCount =
                    int.tryParse(_targetWordCountController.text) ?? 0;
                await Provider.of<AppState>(context, listen: false)
                    .updateTargetWordCount(targetWordCount);
                navigator.pop();
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
      return _buildErrorState();
    }

    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildHeader(context),
            const SizedBox(height: 32),
            _buildProgressSection(appState),
            const SizedBox(height: 32),
            _buildWordCountSection(appState),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Row(
      children: [
        Icon(
          Icons.analytics,
          size: 32,
          color: Theme.of(context).colorScheme.primary,
        ),
        const SizedBox(width: 16),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Story Progress',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            Text(
              'Track your writing journey',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context)
                        .colorScheme
                        .onSurface
                        .withOpacity(0.6),
                  ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildProgressSection(AppState appState) {
    return Row(
      children: [
        Expanded(
          child: _buildProgressCard(
            'Chapters',
            appState.chapters.length,
            Icons.book,
            Theme.of(context).colorScheme.primary,
            true,
            true,
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _buildProgressCard(
            'Codex Entries',
            appState.codexItems.length,
            Icons.list_alt,
            Theme.of(context).colorScheme.secondary,
            true,
            true,
          ),
        ),
      ],
    );
  }

  Widget _buildProgressCard(String title, int value, IconData icon, Color color,
      bool canView, bool canEdit) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: InkWell(
        onTap: () {
          // Navigate based on card type
          if (title == 'Chapters') {
            Navigator.pushNamed(
              context,
              '/chapters',
              arguments: widget.projectId, // Pass only projectId
            ).then((_) => _fetchData());
          } else if (title == 'Codex Entries') {
            Navigator.pushNamed(
              context,
              '/codex',
              arguments: widget.projectId,
            ).then((_) => _fetchData());
          }
        },
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: color, size: 32),
              const SizedBox(height: 16),
              Text(
                title,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              Text(
                value.toString(),
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      color: color,
                      fontWeight: FontWeight.bold,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildWordCountSection(AppState appState) {
    double progress = appState.targetWordCount > 0
        ? min(_wordCount / appState.targetWordCount, 1.0)
        : 0.0;
    Color progressColor = Color.lerp(
      Theme.of(context).colorScheme.error,
      Theme.of(context).colorScheme.primary,
      progress,
    )!;

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Word Count Progress',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                IconButton(
                  icon: const Icon(Icons.edit),
                  onPressed: _showTargetWordCountDialog,
                  tooltip: 'Set Target Word Count',
                ),
              ],
            ),
            const SizedBox(height: 24),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: progress,
                valueColor: AlwaysStoppedAnimation<Color>(progressColor),
                backgroundColor:
                    Theme.of(context).colorScheme.surfaceContainerHighest,
                minHeight: 12,
              ),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  '$_wordCount words',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
                Text(
                  'Target: ${appState.targetWordCount}',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: Theme.of(context)
                            .colorScheme
                            .onSurface
                            .withOpacity(0.6),
                      ),
                ),
              ],
            ),
          ],
        ),
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
            _error,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: Theme.of(context).colorScheme.error,
                ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _fetchData,
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
          ),
        ],
      ),
    );
  }
}
