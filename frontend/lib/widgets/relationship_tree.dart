 import 'package:flutter/material.dart';
 import 'package:graphview/graphview.dart';
 import 'package:graphview/visible_region.dart';

 class RelationshipTree extends StatefulWidget {
   final Map<String, dynamic> graphData;

   const RelationshipTree({Key? key, required this.graphData}) : super(key: key);

   @override
   _RelationshipTreeState createState() => _RelationshipTreeState();
 }

 class _RelationshipTreeState extends State<RelationshipTree> {
   late Graph _graph;
   late VisibleRegion _visibleRegion;

   @override
   void initState() {
     super.initState();
     _graph = Graph()..isTree = true;
     final nodes = <Node>[];
     final edges = <Edge>[];

     // Create nodes
     for (final node in widget.graphData['nodes'] ?? []) {
       nodes.add(Node.Id(node['id']));
     }

     // Create edges
     for (final edge in widget.graphData['edges'] ?? []) {
       final fromNode = nodes.firstWhere((n) => n.key!.value == edge['from']);
       final toNode = nodes.firstWhere((n) => n.key!.value == edge['to']);
       edges.add(Edge(fromNode, toNode));
     }

     _graph.addNodes(nodes);
     _graph.addEdges(edges);
   }

   @override
 Widget build(BuildContext context) {
     _visibleRegion = VisibleRegion.fromContext(context);

     if (widget.graphData['nodes'] == null || widget.graphData['nodes'].isEmpty) {
       return const Center(
         child: Text('No data available'),
       );
     }

     return InteractiveViewer(
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
           if (_visibleRegion.contains(node)) {
             return rectangleWidget(node.key!.value.toString());
           } else {
             return simplifiedRectangleWidget(node.key!.value.toString());
           }
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

   Widget simplifiedRectangleWidget(String name) {
     return Container(
       padding: const EdgeInsets.all(8),
       decoration: BoxDecoration(
         color: Colors.grey,
         borderRadius: BorderRadius.circular(2),
       ),
       child: Text(name),
     );
   }
 }
