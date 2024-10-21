import 'package:flutter/material.dart';
import 'package:graphview/graphview.dart';

class RelationshipTree extends StatefulWidget {
  final Map<String, dynamic> graphData;

  const RelationshipTree({Key? key, required this.graphData}) : super(key: key);

  @override
  _RelationshipTreeState createState() => _RelationshipTreeState();
}

class _RelationshipTreeState extends State<RelationshipTree> {
  late Graph _graph;
  bool _isLoading = true;
  final int _maxNodesPerPage = 20;
  int _currentPage = 0;

  @override
  void initState() {
    super.initState();
    _initializeGraph();
  }

  Future<void> _initializeGraph() async {
    setState(() => _isLoading = true);

    await Future.microtask(() {
      _graph = Graph()..isTree = true;
      final nodes = <Node>[];
      final edges = <Edge>[];

      final startIndex = _currentPage * _maxNodesPerPage;
      final endIndex = ((_currentPage + 1) * _maxNodesPerPage).clamp(0, widget.graphData['nodes'].length);

      // Create nodes
      for (var i = startIndex; i < endIndex; i++) {
        final node = widget.graphData['nodes'][i];
        nodes.add(Node.Id(node['id']));
      }

      // Create edges
      for (final edge in widget.graphData['edges'] ?? []) {
        final fromNode = nodes.firstWhere((n) => n.key!.value == edge['from'], orElse: () => null);
        final toNode = nodes.firstWhere((n) => n.key!.value == edge['to'], orElse: () => null);
        if (fromNode != null && toNode != null) {
          edges.add(Edge(fromNode, toNode, paint: Paint()..color = Colors.green));
        }
      }

      _graph.addNodes(nodes);
      _graph.addEdges(edges);
    });

    setState(() => _isLoading = false);
  }

  @override
  Widget build(BuildContext context) {
    if (widget.graphData['nodes'] == null || widget.graphData['nodes'].isEmpty) {
      return const Center(
        child: Text('No data available'),
      );
    }

    if (_isLoading) {
      return const Center(
        child: CircularProgressIndicator(),
      );
    }

    return Column(
      children: [
        Expanded(
          child: InteractiveViewer(
            constrained: false,
            boundaryMargin: const EdgeInsets.all(100),
            minScale: 0.01,
            maxScale: 5.6,
            child: GraphView(
              graph: _graph,
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
          ),
        ),
        if (widget.graphData['nodes'].length > (_currentPage + 1) * _maxNodesPerPage)
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: ElevatedButton(
              onPressed: () {
                setState(() {
                  _currentPage++;
                  _initializeGraph();
                });
              },
              child: Text('Load More'),
            ),
          ),
      ],
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
