import 'package:flutter/material.dart';
import 'package:flutter_graph/flutter_graph.dart';

class RelationshipTree extends StatefulWidget {
  final Map<String, dynamic> graphData;

  const RelationshipTree({Key? key, required this.graphData}) : super(key: key);

  @override
  _RelationshipTreeState createState() => _RelationshipTreeState();
}

class _RelationshipTreeState extends State<RelationshipTree> {
  late GraphData _graphData;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _graphData = GraphData(nodes: widget.graphData['nodes'], edges: widget.graphData['edges']);
    _isLoading = false;
  }

  @override
  Widget build(BuildContext context) {
    return _isLoading
        ? const Center(child: CircularProgressIndicator())
        : GraphView(
            graphData: _graphData,
            nodeBuilder: (context, node) {
              return Container(
                width: 50,
                height: 50,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.blue,
                ),
                child: Center(
                  child: Text(node.data['label']),
                ),
              );
            },
            edgeBuilder: (context, edge) {
              return Container(
                width: 2,
                height: 50,
                color: Colors.grey,
              );
            },
            virtualization: true,
          );
  }
}
