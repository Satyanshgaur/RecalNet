import sqlite3
import json
import networkx as nx
from pathlib import Path
from uuid import UUID
from datetime import datetime
from typing import Optional
from graphmem.graph.models import Node, Edge, Episode
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
            # Episodes Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    document_id TEXT,
                    chunk_id TEXT,
                    raw_text TEXT,
                    created_at TEXT
                )
            """)
            # Node Mentions (Mapping node to episodes)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS node_mentions (
                    node_id TEXT,
                    episode_id TEXT,
                    PRIMARY KEY (node_id, episode_id),
                    FOREIGN KEY(node_id) REFERENCES nodes(id),
                    FOREIGN KEY(episode_id) REFERENCES episodes(id)
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
            
            # Check and add new columns to edges if they don't exist
            cursor.execute("PRAGMA table_info(edges)")
            columns = {row[1] for row in cursor.fetchall()}
            
            new_edge_columns = {
                "fact": "TEXT",
                "supporting_episode_ids": "TEXT",
                "support_count": "INTEGER DEFAULT 1",
                "valid_from": "TEXT",
                "valid_to": "TEXT",
                "evidence_reference": "TEXT"
            }
            for col_name, col_type in new_edge_columns.items():
                if col_name not in columns:
                    cursor.execute(f"ALTER TABLE edges ADD COLUMN {col_name} {col_type}")

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
            cursor.execute("DELETE FROM node_mentions")
            cursor.execute("DELETE FROM nodes")
            cursor.execute("DELETE FROM episodes")
            
            # Insert Episodes
            episodes = graph.graph.get("episodes", {})
            for ep_id, ep in episodes.items():
                cursor.execute("""
                    INSERT INTO episodes (id, document_id, chunk_id, raw_text, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    str(ep.id),
                    ep.document_id,
                    ep.chunk_id,
                    ep.raw_text,
                    ep.created_at.isoformat()
                ))
            
            # Insert Node Mentions
            node_to_episodes = graph.graph.get("node_to_episodes", {})
            for node_id, ep_ids in node_to_episodes.items():
                for ep_id in ep_ids:
                    cursor.execute("""
                        INSERT INTO node_mentions (node_id, episode_id)
                        VALUES (?, ?)
                    """, (str(node_id), str(ep_id)))
            
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
                # Convert UUIDs to strings for JSON storage
                evidence_ref_dict = None
                if edge.evidence_reference:
                    evidence_ref_dict = {
                        k: (str(v) if isinstance(v, UUID) else v)
                        for k, v in edge.evidence_reference.items()
                    }
                cursor.execute("""
                    INSERT INTO edges (
                        id, source_node_id, target_node_id, relation, properties, confidence,
                        created_at, fact, supporting_episode_ids, support_count,
                        valid_from, valid_to, evidence_reference
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(edge.id),
                    str(edge.source_node_id),
                    str(edge.target_node_id),
                    edge.relation,
                    json.dumps(edge.properties),
                    edge.confidence,
                    edge.created_at.isoformat(),
                    edge.fact,
                    json.dumps([str(ep_id) for ep_id in edge.supporting_episode_ids]),
                    edge.support_count,
                    edge.valid_from.isoformat() if edge.valid_from else None,
                    edge.valid_to.isoformat() if edge.valid_to else None,
                    json.dumps(evidence_ref_dict) if evidence_ref_dict else None
                ))
            conn.commit()

    def load(self) -> GraphStore:
        """Reconstructs the GraphStore from SQLite."""
        store = GraphStore()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Load Episodes
            cursor.execute("SELECT * FROM episodes")
            for row in cursor.fetchall():
                episode = Episode(
                    id=UUID(row["id"]),
                    document_id=row["document_id"],
                    chunk_id=row["chunk_id"],
                    raw_text=row["raw_text"],
                    created_at=datetime.fromisoformat(row["created_at"])
                )
                store.add_episode(episode)
                
            # Load Node Mentions
            cursor.execute("SELECT * FROM node_mentions")
            for row in cursor.fetchall():
                store.add_node_mention(
                    node_id=UUID(row["node_id"]),
                    episode_id=UUID(row["episode_id"])
                )
            
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
                supporting_episode_ids = []
                if "supporting_episode_ids" in row.keys() and row["supporting_episode_ids"]:
                    supporting_episode_ids = [UUID(uid) for uid in json.loads(row["supporting_episode_ids"])]
                
                valid_from = None
                if "valid_from" in row.keys() and row["valid_from"]:
                    valid_from = datetime.fromisoformat(row["valid_from"])
                
                valid_to = None
                if "valid_to" in row.keys() and row["valid_to"]:
                    valid_to = datetime.fromisoformat(row["valid_to"])
                
                evidence_reference = None
                if "evidence_reference" in row.keys() and row["evidence_reference"]:
                    evidence_reference = json.loads(row["evidence_reference"])
                    if "episode_id" in evidence_reference and evidence_reference["episode_id"]:
                        evidence_reference["episode_id"] = UUID(evidence_reference["episode_id"])
                
                edge = Edge(
                    id=UUID(row["id"]),
                    source_node_id=UUID(row["source_node_id"]),
                    target_node_id=UUID(row["target_node_id"]),
                    relation=row["relation"],
                    properties=json.loads(row["properties"]),
                    confidence=row["confidence"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    fact=row["fact"] if "fact" in row.keys() else None,
                    supporting_episode_ids=supporting_episode_ids,
                    support_count=row["support_count"] if ("support_count" in row.keys() and row["support_count"] is not None) else 1,
                    valid_from=valid_from,
                    valid_to=valid_to,
                    evidence_reference=evidence_reference
                )
                store.add_edge(edge)

        return store

