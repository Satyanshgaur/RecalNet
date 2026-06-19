import networkx as nx
from typing import List, Optional, Dict, Any
from uuid import UUID
from graphmem.graph.models import Node, Edge, Episode


class GraphStore:
    """
    In-memory graph store wrapping NetworkX.
    """
    
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self.episodes = self.graph.graph.setdefault("episodes", {})
        self.edges = self.graph.graph.setdefault("edges", {})
        self.node_to_episodes = self.graph.graph.setdefault("node_to_episodes", {})

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
        self.edges[edge.id] = edge

    def add_episode(self, episode: Episode) -> None:
        """Register an episode (source evidence)."""
        self.episodes[episode.id] = episode

    def get_episode(self, episode_id: UUID) -> Optional[Episode]:
        """Retrieve an episode by its ID."""
        return self.episodes.get(episode_id)

    def add_node_mention(self, node_id: UUID, episode_id: UUID) -> None:
        """Record that an episode mentions a node."""
        if node_id not in self.node_to_episodes:
            self.node_to_episodes[node_id] = []
        if episode_id not in self.node_to_episodes[node_id]:
            self.node_to_episodes[node_id].append(episode_id)

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
            # Clean up edge dictionary references
            for source, target, key in list(self.graph.edges(node_id, keys=True)):
                self.edges.pop(key, None)
            for source, target, key in list(self.graph.in_edges(node_id, keys=True)):
                self.edges.pop(key, None)
            self.graph.remove_node(node_id)
            self.node_to_episodes.pop(node_id, None)

    def explain_node(self, node_id: UUID) -> Dict[str, Any]:
        """Explain a node by listing its metadata and all episodes mentioning it."""
        node = self.get_node(node_id)
        if not node:
            raise ValueError(f"Node {node_id} does not exist.")
        episode_ids = self.node_to_episodes.get(node_id, [])
        mentioned_in = [self.episodes[ep_id] for ep_id in episode_ids if ep_id in self.episodes]
        return {
            "node": node,
            "mentioned_in": mentioned_in
        }

    def explain_edge(self, edge_id: UUID) -> Dict[str, Any]:
        """Explain an edge by showing its semantic fact, confidence, and supporting episodes."""
        edge = self.edges.get(edge_id)
        if not edge:
            # Fallback to search in graph if not in edge registry
            for _, _, key, data in self.graph.edges(keys=True, data=True):
                if key == edge_id:
                    edge = data["data"]
                    self.edges[edge_id] = edge
                    break
        if not edge:
            raise ValueError(f"Edge {edge_id} does not exist.")
        
        supporting_episodes = [
            self.episodes[ep_id] for ep_id in edge.supporting_episode_ids if ep_id in self.episodes
        ]
        return {
            "fact": edge.fact,
            "supporting_episodes": supporting_episodes,
            "confidence": edge.confidence
        }

