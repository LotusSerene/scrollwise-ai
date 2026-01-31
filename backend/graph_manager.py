import networkx as nx
import logging
from typing import List, Dict, Any, Optional, Set

class GraphManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.graph = nx.Graph()

    def build_graph(
        self,
        codex_items: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        locations: List[Dict[str, Any]],
        event_connections: List[Dict[str, Any]],
        location_connections: List[Dict[str, Any]],
    ):
        """Builds the graph from the provided data."""
        self.graph.clear()
        self.logger.debug("Building knowledge graph...")

        # Add Codex Items (Characters, Factions, etc.)
        for item in codex_items:
            self.graph.add_node(
                item["id"],
                type=item.get("type", "unknown"),
                name=item.get("name", "Unknown"),
                description=item.get("description", "")
            )

        # Add Locations
        for loc in locations:
            self.graph.add_node(
                loc["id"],
                type="location",
                name=loc.get("name", "Unknown Location"),
                description=loc.get("description", "")
            )

        # Add Events
        for evt in events:
            self.graph.add_node(
                evt["id"],
                type="event",
                name=evt.get("title", "Unknown Event"),
                description=evt.get("description", "")
            )
            # Event -> Character (participation)
            if evt.get("character_id"):
                self.graph.add_edge(evt["id"], evt["character_id"], relation="involved_character")
            # Event -> Location (location)
            if evt.get("location_id"):
                self.graph.add_edge(evt["id"], evt["location_id"], relation="occurred_at")

        # Add Character Relationships
        for rel in relationships:
            self.graph.add_edge(
                rel["character_id"],
                rel["related_character_id"],
                relation=rel.get("relationship_type", "related"),
                description=rel.get("description", "")
            )

        # Add Event Connections
        for conn in event_connections:
            self.graph.add_edge(
                conn["event1_id"],
                conn["event2_id"],
                relation=conn.get("connection_type", "connected"),
                description=conn.get("description", "")
            )

        # Add Location Connections
        for conn in location_connections:
            self.graph.add_edge(
                conn["location1_id"],
                conn["location2_id"],
                relation=conn.get("connection_type", "connected"),
                description=conn.get("description", "")
            )

        self.logger.debug(f"Graph built with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges.")

    def get_related_context(self, entity_names: List[str], depth: int = 1) -> str:
        """
        Retrieves related context for the given entity names.
        """
        if not entity_names:
            return ""

        # Create name-to-ID mapping from current graph nodes
        name_to_id = {}
        for node_id, data in self.graph.nodes(data=True):
            if "name" in data:
                name_to_id[data["name"].lower()] = node_id

        found_nodes = []
        for name in entity_names:
            normalized_name = name.lower().strip()
            # Try exact match
            if normalized_name in name_to_id:
                found_nodes.append(name_to_id[normalized_name])
            else:
                # Try partial match (simple)
                for graph_name, node_id in name_to_id.items():
                    if normalized_name in graph_name or graph_name in normalized_name:
                        found_nodes.append(node_id)
                        break # Take first match

        if not found_nodes:
            return ""

        context_lines = []
        visited_edges = set()

        for start_node in found_nodes:
            # Get ego graph (subgraph of neighbors up to depth)
            try:
                ego_graph = nx.ego_graph(self.graph, start_node, radius=depth)
            except Exception as e:
                self.logger.warning(f"Error getting ego graph for {start_node}: {e}")
                continue
            
            for u, v, data in ego_graph.edges(data=True):
                edge_key = tuple(sorted((u, v)))
                if edge_key in visited_edges:
                    continue
                visited_edges.add(edge_key)

                u_name = self.graph.nodes[u].get("name", "Unknown")
                v_name = self.graph.nodes[v].get("name", "Unknown")
                relation = data.get("relation", "related to")
                desc = data.get("description", "")

                line = f"- {u_name} is {relation} {v_name}"
                if desc:
                    line += f": {desc}"
                context_lines.append(line)

        if not context_lines:
             return ""

        return "Graph Relationships (Contextual Connections):\n" + "\n".join(context_lines)
