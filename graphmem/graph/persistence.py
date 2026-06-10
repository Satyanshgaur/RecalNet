import sqlite3
import json
import networkx as nx
from pathlib import Path
from uuid import UUID
from datetime import datetime
from typing import Optional
from graphmem.graph.models import Node, Edge
from graphmem.graph.store import GraphStore
from graphmem.core.config import settings

class GraphPersistence:
    """
    Handles SQLite persistence for the GraphStore.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.sqlite_path
        self._init_db()

    def _init_db(self):
        """Create tables and indices if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Nodes Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    label TEXT,
                    name TEXT,
                    properties TEXT,
                    confidence REAL,
                    created_at TEXT,
                    updated_at TEXT,
                    sources TEXT
                )
            """)
            # Edges Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    id TEXT PRIMARY KEY,
                    source_node_id TEXT,
                    target_node_id TEXT,
                    relation TEXT,
                    properties TEXT,
                    confidence REAL,
                    created_at TEXT,
                    FOREIGN KEY(source_node_id) REFERENCES nodes(id),
                    FOREIGN KEY(target_node_id) REFERENCES nodes(id)
                )
            """)
            # Indices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_label ON nodes(label)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_node_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_node_id)")
            conn.commit()

    def save(self, graph: nx.MultiDiGraph) -> None:
        """Persists the full graph to SQLite (Full Replace)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # We do a full replace for simplicity and correctness as requested
            cursor.execute("DELETE FROM edges")
            cursor.execute("DELETE FROM nodes")
            
            # Insert Nodes
            for _, data in graph.nodes(data=True):
                node: Node = data["data"]
                cursor.execute("""
                    INSERT INTO nodes (id, label, name, properties, confidence, created_at, updated_at, sources)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(node.id),
                    node.label,
                    node.name,
                    json.dumps(node.properties),
                    node.confidence,
                    node.created_at.isoformat(),
                    node.updated_at.isoformat(),
                    json.dumps(node.sources)
                ))
            
            # Insert Edges
            for _, _, attr in graph.edges(data=True):
                edge: Edge = attr["data"]
                cursor.execute("""
                    INSERT INTO edges (id, source_node_id, target_node_id, relation, properties, confidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(edge.id),
                    str(edge.source_node_id),
                    str(edge.target_node_id),
                    edge.relation,
                    json.dumps(edge.properties),
                    edge.confidence,
                    edge.created_at.isoformat()
                ))
            conn.commit()

    def load(self) -> GraphStore:
        """Reconstructs the GraphStore from SQLite."""
        store = GraphStore()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Load Nodes
            cursor.execute("SELECT * FROM nodes")
            for row in cursor.fetchall():
                node = Node(
                    id=UUID(row["id"]),
                    label=row["label"],
                    name=row["name"],
                    properties=json.loads(row["properties"]),
                    confidence=row["confidence"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    sources=json.loads(row["sources"])
                )
                store.add_node(node)
                
            # Load Edges
            cursor.execute("SELECT * FROM edges")
            for row in cursor.fetchall():
                edge = Edge(
                    id=UUID(row["id"]),
                    source_node_id=UUID(row["source_node_id"]),
                    target_node_id=UUID(row["target_node_id"]),
                    relation=row["relation"],
                    properties=json.loads(row["properties"]),
                    confidence=row["confidence"],
                    created_at=datetime.fromisoformat(row["created_at"])
                )
                store.add_edge(edge)
                
        return store
