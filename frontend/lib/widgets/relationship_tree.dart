import 'package:flutter/material.dart';
import 'package:flutter_graph/flutter_graph.dart';

class RelationshipTree extends StatelessWidget {
  final Map<String, dynamic> graphData;

  const RelationshipTree({Key? key, required this.graphData}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final graph = Graph(
      nodes: graphData['nodes']?.map((node) => Node(id: node['id'])).toList() ?? [],
      edges: graphData['edges']?.map((edge) => Edge(from: edge['from'], to: edge['to'])).toList() ?? [],
    );

    return VirtualizedGraphView(
      graph: graph,
      nodeBuilder: (node) {
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.red,
            borderRadius: BorderRadius.circular(4),
            boxShadow: const [
              BoxShadow(color: Colors.black26, spreadRadius: 1, blurRadius: 2)
            ],
          ),
          child: Text(node.id),
        );
      },
      edgeBuilder: (edge) {
        return Container(
          decoration: BoxDecoration(
            color: Colors.green,
            shape: BoxShape.rectangle,
          ),
        );
      },
      loadingIndicator: const CircularProgressIndicator(),
    );
  }

  Widget rectangleWidget(String name) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.red,
        borderRadius: BorderRadius.circular(4),
        boxShadow: const [
          BoxShadow(color: Colors.black26, spreadRadius: 1, blurRadius: 2)
        ],
      ),
      child: Text(name),
    );
  }
}
