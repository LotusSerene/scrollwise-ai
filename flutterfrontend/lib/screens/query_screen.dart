import 'package:flutter/material.dart';
import '../components/query.dart';

class QueryScreen extends StatelessWidget {
  const QueryScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Query(),
    );
  }
}
