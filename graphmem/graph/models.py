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
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    sources: List[str] = Field(default_factory=list)


class Edge(BaseModel):
    """
    Represents a relationship between two nodes.
    """
    id: UUID = Field(default_factory=uuid4)
    source_node_id: UUID
    target_node_id: UUID
    relation: str  # e.g., "FOUNDED", "CEO_OF", "LOCATED_IN"
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
