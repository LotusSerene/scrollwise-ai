import 'package:flutter/material.dart';
import '../components/validity.dart';

class ValidityScreen extends StatelessWidget {
  final String projectId;
  const ValidityScreen({Key? key, required this.projectId}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Validity')),
      body: Validity(projectId: projectId),
    );
  }
}