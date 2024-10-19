import 'package:flutter/material.dart';
import '../components/create_chapter.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/constants.dart';
import '../utils/auth.dart';
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
      appBar: AppBar(title: const Text('Create')),
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Consumer<PresetProvider>(
                builder: (context, presetProvider, child) {
                  if (presetProvider.isLoading) {
                    return CircularProgressIndicator();
                  }
                  return DropdownButton<String>(
                    value: presetProvider.selectedPreset,
                    hint: Text('Select a preset'),
                    onChanged: (String? newValue) {
                      if (newValue != null) {
                        presetProvider.loadPreset(newValue, widget.projectId);
                      }
                    },
                    items: presetProvider.presets
                        .map<DropdownMenuItem<String>>((String value) {
                      return DropdownMenuItem<String>(
                        value: value,
                        child: Text(value),
                      );
                    }).toList(),
                  );
                },
              ),
              SizedBox(height: 16),
              CreateChapter(projectId: widget.projectId),
            ],
          ),
        ),
      ),
    );
  }
}
