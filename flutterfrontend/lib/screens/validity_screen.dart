import 'package:flutter/material.dart';
import '../components/validity.dart';

class ValidityScreen extends StatelessWidget {
  const ValidityScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Validity')),
      body: const Validity(),
    );
  }
}
