import 'package:flutter/material.dart';
import '../components/create_chapter.dart';
import '../providers/preset_provider.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';

class CreateScreen extends StatefulWidget {
  final String projectId;
  const CreateScreen({Key? key, required this.projectId}) : super(key: key);

  @override
  _CreateScreenState createState() => _CreateScreenState();
}

class _CreateScreenState extends State<CreateScreen> {
  Future<bool> _onWillPop() async {
    final appState = Provider.of<AppState>(context, listen: false);
    if (appState.chapterCreationState['isGenerating']) {
      final shouldLeave = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Generation in Progress'),
          content: const Text(
              'Chapter generation is still in progress. Are you sure you want to leave?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('Stay'),
            ),
            TextButton(
              onPressed: () {
                appState.cancelChapterGeneration();
                Navigator.of(context).pop(true);
              },
              child: const Text('Leave'),
            ),
          ],
        ),
      );
      return shouldLeave ?? false;
    }
    return true;
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<PresetProvider>(context, listen: false)
          .fetchPresets(widget.projectId);
    });
  }

  @override
  Widget build(BuildContext context) {
    return WillPopScope(
      onWillPop: _onWillPop,
      child: Scaffold(
        appBar: AppBar(
          elevation: 0,
          title: Row(
            children: [
              Icon(Icons.create_new_folder,
                  color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 12),
              const Text('Create New Chapter'),
            ],
          ),
        ),
        body: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                Theme.of(context).colorScheme.surface,
                Theme.of(context).colorScheme.surface.withOpacity(0.8),
              ],
            ),
          ),
          child: CreateChapter(projectId: widget.projectId),
        ),
      ),
    );
  }
}
