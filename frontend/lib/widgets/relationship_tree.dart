import 'package:flutter/material.dart';
import 'package:graphview/GraphView.dart';

class RelationshipTree extends StatelessWidget {
  final Map<String, dynamic> graphData;

  const RelationshipTree({Key? key, required this.graphData}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final Graph graph = Graph()..isTree = false;
    final nodes = <Node>[];
    final edges = <Edge>[];

    // Create nodes
    for (var nodeData in graphData['nodes']) {
      nodes.add(Node.Id(nodeData['id']));
    }

    // Create edges
    for (var edgeData in graphData['edges']) {
      if (edgeData['from'] != null && edgeData['to'] != null) {
        edges.add(Edge(
          nodes.firstWhere((node) => node.key?.value == edgeData['from']),
          nodes.firstWhere((node) => node.key?.value == edgeData['to']),
          paint: Paint()..color = Colors.blue..strokeWidth = 2,
        ));
      }
    }

    graph.addNodes(nodes);
    graph.addEdges(edges);

    return InteractiveViewer(
      constrained: false,
      boundaryMargin: EdgeInsets.all(100),
      minScale: 0.01,
      maxScale: 5.6,
      child: GraphView(
        graph: graph,
        algorithm: FruchtermanReingoldAlgorithm(iterations: 1000),
        paint: Paint()
          ..color = Colors.black
          ..strokeWidth = 1
          ..style = PaintingStyle.stroke,
        builder: (Node node) {
          return Container(
            padding: EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.blue[100],
              shape: BoxShape.circle,
            ),
            child: Text(
              node.key!.value as String,
              style: TextStyle(color: Colors.black),
            ),
          );
        },
      ),
    );
  }
}
