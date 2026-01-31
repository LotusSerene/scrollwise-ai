"use client";

import React, { useMemo, useCallback, useEffect } from "react"; // Added useEffect
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Position,
  MarkerType,
  Connection,
  Edge,
  Node,
} from "reactflow";

import "reactflow/dist/style.css"; // Import default styles
import { CodexEntry, Relationship } from "@/types";

interface RelationshipGraphProps {
  characters: CodexEntry[];
  relationships: Relationship[];
}

// Helper function to get CSS variable value (client-side only)
const getCssVariable = (variableName: string): string => {
  if (typeof window === 'undefined') {
    // Provide sensible fallbacks for SSR or initial render
    if (variableName === '--card') return '#2d3748'; // gray-800 fallback
    if (variableName === '--card-foreground') return '#e2e8f0'; // gray-200 fallback
    if (variableName === '--border') return '#4a5568'; // gray-600 fallback
    if (variableName === '--muted-foreground') return '#a0aec0'; // gray-400 fallback
    if (variableName === '--background') return '#1a202c'; // gray-900 fallback
    return '#ffffff'; // Default fallback
  }
  return getComputedStyle(document.documentElement).getPropertyValue(variableName).trim();
};

export function RelationshipGraph({
  characters,
  relationships,
}: RelationshipGraphProps) {
  // State to hold computed theme colors
  const [themeColors, setThemeColors] = React.useState({
    nodeBg: '#2d3748',
    nodeColor: '#e2e8f0',
    nodeBorder: '#4a5568',
    edgeStroke: '#718096',
    labelColor: '#a0aec0',
    labelBg: '#2d3748',
    minimapBg: '#1a202c',
    minimapNode: '#4a5568',
    backgroundGrid: '#4a5568',
  });

  // Effect to compute colors on mount (client-side)
  useEffect(() => {
    setThemeColors({
      nodeBg: getCssVariable('--card'),
      nodeColor: getCssVariable('--card-foreground'),
      nodeBorder: getCssVariable('--border'),
      edgeStroke: getCssVariable('--muted-foreground'), // Use muted for edges
      labelColor: getCssVariable('--muted-foreground'),
      labelBg: getCssVariable('--card'), // Use card bg for label bg
      minimapBg: getCssVariable('--background'), // Use main background
      minimapNode: getCssVariable('--border'), // Use border color for minimap nodes
      backgroundGrid: getCssVariable('--border'), // Use border color for grid
    });
  }, []);

  // --- Convert data to ReactFlow format ---
  const { initialNodes, initialEdges } = useMemo(() => {
    // Define styles using state variables
    const nodeStyles: React.CSSProperties = {
      background: themeColors.nodeBg,
      color: themeColors.nodeColor,
      border: `1px solid ${themeColors.nodeBorder}`,
      borderRadius: "var(--radius-md, 6px)", // Use theme radius if available
      padding: "10px 15px",
      minWidth: "150px",
      textAlign: "center",
      fontSize: "14px",
    };

    const edgeStyles: React.CSSProperties = {
      strokeWidth: 1.5,
      stroke: themeColors.edgeStroke,
    };

    const markerEnd = {
      type: MarkerType.ArrowClosed,
      width: 20,
      height: 20,
      color: themeColors.edgeStroke,
    };

    const nodes: Node[] = characters.map((char, index) => ({
      id: char.id,
      type: "default",
      data: { label: char.name },
      position: { x: (index % 5) * 250, y: Math.floor(index / 5) * 150 },
      style: nodeStyles,
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    }));

    const edges: Edge[] = relationships.map((rel) => ({
      id: `e-${rel.id}`,
      source: rel.character_id,
      target: rel.related_character_id,
      label: rel.relationship_type,
      labelStyle: { fill: themeColors.labelColor, fontSize: 10 },
      labelBgPadding: [4, 2],
      labelBgBorderRadius: 4, // Use a fixed value or theme radius
      labelBgStyle: { fill: themeColors.labelBg, fillOpacity: 0.7 },
      type: "smoothstep",
      style: edgeStyles,
      markerEnd: markerEnd,
    }));

    return { initialNodes: nodes, initialEdges: edges };
  }, [characters, relationships, themeColors]); // Recalculate when data or themeColors change

  // --- ReactFlow State Hooks ---
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Reset layout if data changes significantly
  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  // Handle adding new connections (optional)
  const onConnect = useCallback(
    (params: Connection | Edge) =>
      setEdges((eds: Edge[]) => addEdge(params, eds)),
    [setEdges]
  );

  if (!characters || characters.length === 0) {
    return (
      // Apply theme style
      <p className="text-center text-muted-foreground py-4">
        No characters to display in graph.
      </p>
    );
  }
  if (!relationships || relationships.length === 0) {
    return (
      // Apply theme style
      <p className="text-center text-muted-foreground py-4">
        No relationships to display in graph.
      </p>
    );
  }

  return (
    // Apply theme styles to container
    <div
      style={{ height: "60vh", width: "100%" }}
      className="bg-background border border-border rounded-lg mt-6" // Use theme background/border
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        fitView
        nodesDraggable={true}
        className="relationship-graph-flow"
      >
        <Controls
          className="react-flow__controls"
          style={{ bottom: 10, left: 10 }}
        />
        <MiniMap
          nodeColor={() => themeColors.minimapNode} // Use theme color
          nodeStrokeWidth={3}
          zoomable
          pannable
          style={{
            bottom: 10,
            right: 10,
            height: 100,
            backgroundColor: themeColors.minimapBg, // Use theme color
            border: `1px solid ${themeColors.nodeBorder}` // Add border consistent with nodes
          }}
        />
        <Background color={themeColors.backgroundGrid} gap={16} /> {/* Use theme color */}
      </ReactFlow>
    </div>
  );
}
