import 'package:flutter/material.dart';
import '../components/create_chapter.dart';
import '../providers/preset_provider.dart';
import 'package:provider/provider.dart';

class CreateScreen extends StatefulWidget {
  final String projectId;
  const CreateScreen({Key? key, required this.projectId}) : super(key: key);

  @override
  _CreateScreenState createState() => _CreateScreenState();
}

class _CreateScreenState extends State<CreateScreen> {
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
    return Scaffold(
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
    );
  }
}
