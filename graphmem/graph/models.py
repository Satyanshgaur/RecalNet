from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class Node(BaseModel):
    """
    Represents a single entity in the graph.
    """
    id: UUID = Field(default_factory=uuid4)
    label: str  # e.g., "Person", "Company", "Location"
    name: str   # e.g., "Elon Musk"
    aliases: List[str] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    sources: List[str] = Field(default_factory=list)


class Episode(BaseModel):
    """
    Represents a single source evidence block / raw text chunk.
    """
    id: UUID = Field(default_factory=uuid4)
    document_id: str
    chunk_id: str
    raw_text: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Edge(BaseModel):
    """
    Represents an enriched relationship between two nodes.
    """
    id: UUID = Field(default_factory=uuid4)
    source_node_id: UUID
    target_node_id: UUID
    relation: str  # e.g., "FOUNDED", "CEO_OF", "LOCATED_IN"
    confidence: float = 1.0
    fact: Optional[str] = None
    supporting_episode_ids: List[UUID] = Field(default_factory=list)
    support_count: int = 1
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    evidence_reference: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    properties: Dict[str, Any] = Field(default_factory=dict)

