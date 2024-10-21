import 'package:flutter/material.dart';
import 'package:graphview/GraphView.dart';

class RelationshipTree extends StatelessWidget {
  final Map<String, dynamic> graphData;

  const RelationshipTree({Key? key, required this.graphData}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final Graph graph = Graph()..isTree = true;
    final nodes = <Node>[];
    final edges = <Edge>[];

    // Create nodes
    for (final node in graphData['nodes'] ?? []) {
      nodes.add(Node.Id(node['id']));
    }

    // Create edges
    for (final edge in graphData['edges'] ?? []) {
      final fromNode = nodes.firstWhere((n) => n.key!.value == edge['from']);
      final toNode = nodes.firstWhere((n) => n.key!.value == edge['to']);
      edges.add(Edge(fromNode, toNode));
    }

    graph.addNodes(nodes);
    graph.addEdges(edges);

    return InteractiveViewer(
      constrained: false,
      boundaryMargin: const EdgeInsets.all(100),
      minScale: 0.01,
      maxScale: 5.6,
      child: GraphView(
        graph: graph,
        algorithm: BuchheimWalkerAlgorithm(
          BuchheimWalkerConfiguration(),
          TreeEdgeRenderer(BuchheimWalkerConfiguration()),
        ),
        paint: Paint()
          ..color = Colors.green
          ..strokeWidth = 1
          ..style = PaintingStyle.stroke,
        builder: (Node node) {
          return rectangleWidget(node.key!.value.toString());
        },
      ),
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
