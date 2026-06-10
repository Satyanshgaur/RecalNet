import networkx as nx
from typing import List, Optional, Dict, Any
from uuid import UUID
from graphmem.graph.models import Node, Edge


class GraphStore:
    """
    In-memory graph store wrapping NetworkX.
    """
    
    def __init__(self):
        self.graph = nx.MultiDiGraph()

    def add_node(self, node: Node) -> None:
        """Add a node to the graph."""
        self.graph.add_node(
            node.id, 
            data=node,
            name=node.name,
            label=node.label
        )

    def add_edge(self, edge: Edge) -> None:
        """Add an edge to the graph."""
        # Ensure nodes exist (standard graph practice, though MultiDiGraph adds nodes if missing)
        if not self.graph.has_node(edge.source_node_id):
            raise ValueError(f"Source node {edge.source_node_id} does not exist.")
        if not self.graph.has_node(edge.target_node_id):
            raise ValueError(f"Target node {edge.target_node_id} does not exist.")
        
        self.graph.add_edge(
            edge.source_node_id,
            edge.target_node_id,
            key=edge.id,
            data=edge,
            relation=edge.relation
        )

    def get_node(self, node_id: UUID) -> Optional[Node]:
        """Retrieve a node by its ID."""
        node_data = self.graph.nodes.get(node_id)
        return node_data["data"] if node_data else None

    def find_nodes_by_name(self, name: str) -> List[Node]:
        """Find nodes matching a specific name."""
        return [
            data["data"] 
            for _, data in self.graph.nodes(data=True) 
            if data.get("name") == name
        ]

    def find_nodes_by_label(self, label: str) -> List[Node]:
        """Find nodes matching a specific label."""
        return [
            data["data"] 
            for _, data in self.graph.nodes(data=True) 
            if data.get("label") == label
        ]

    def get_neighbors(self, node_id: UUID) -> List[Dict[str, Any]]:
        """Get all adjacent nodes and the edges connecting to them."""
        neighbors = []
        # Successors (Out-edges)
        for target_id in self.graph.successors(node_id):
            edge_data_dict = self.graph.get_edge_data(node_id, target_id)
            for edge_id, attr in edge_data_dict.items():
                neighbors.append({
                    "node": self.get_node(target_id),
                    "edge": attr["data"],
                    "direction": "outbound"
                })
        
        # Predecessors (In-edges)
        for source_id in self.graph.predecessors(node_id):
            edge_data_dict = self.graph.get_edge_data(source_id, node_id)
            for edge_id, attr in edge_data_dict.items():
                neighbors.append({
                    "node": self.get_node(source_id),
                    "edge": attr["data"],
                    "direction": "inbound"
                })
        return neighbors

    def delete_node(self, node_id: UUID) -> None:
        """Delete a node and all its associated edges."""
        if self.graph.has_node(node_id):
            self.graph.remove_node(node_id)
