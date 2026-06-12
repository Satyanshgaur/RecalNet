import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from uuid import uuid4

from graphmem.graph.models import Node, Edge
from graphmem.graph.store import GraphStore
from graphmem.agents.extractor import Extractor
from graphmem.memory.merger import NodeMerger

logger = logging.getLogger(__name__)

class SimpleRecursiveSplitter:
    """
    A simple recursive character splitter to chunk text.
    """
    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", ". ", " ", ""]

    def split_text(self, text: str) -> List[str]:
        return self._split(text, self.separators)

    def _split(self, text: str, separators: List[str]) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text]
        
        separator = separators[0]
        remaining_separators = separators[1:]
        
        splits = text.split(separator)
        final_chunks = []
        current_chunk = ""
        
        for s in splits:
            # If a single split is already too big, recurse on it
            if len(s) > self.chunk_size:
                if current_chunk:
                    final_chunks.append(current_chunk)
                    current_chunk = ""
                final_chunks.extend(self._split(s, remaining_separators))
            # If adding this split exceeds size, save current and start new with overlap
            elif len(current_chunk) + len(s) + len(separator) > self.chunk_size:
                if current_chunk:
                    final_chunks.append(current_chunk)
                # Simple overlap: take the end of the previous chunk
                overlap_start = max(0, len(current_chunk) - self.chunk_overlap)
                current_chunk = current_chunk[overlap_start:] + separator + s
            else:
                if current_chunk:
                    current_chunk += separator + s
                else:
                    current_chunk = s
                    
        if current_chunk:
            final_chunks.append(current_chunk)
            
        return final_chunks

class DocumentIngester:
    """
    Orchestrates the process of turning a document into graph components.
    """
    def __init__(self, store: GraphStore, extractor: Optional[Extractor] = None):
        self.store = store
        self.extractor = extractor or Extractor()
        self.merger = NodeMerger(store)
        # 512 tokens ~ 2000 chars, 64 tokens ~ 250 chars
        self.splitter = SimpleRecursiveSplitter(chunk_size=2000, chunk_overlap=250)

    async def ingest(self, source: str, source_id: Optional[str] = None) -> None:
        """
        Ingest text or a file path.
        """
        text = source
        # Robustly check if source is a file path
        is_file = False
        if len(source) < 255: # Max path length on most systems
            try:
                p = Path(source)
                if p.is_file():
                    is_file = True
            except Exception:
                pass

        if is_file:
            with open(source, "r", encoding="utf-8") as f:
                text = f.read()
            source_id = source_id or source
        
        source_id = source_id or "manual_input"
        
        chunks = self.splitter.split_text(text)
        logger.info(f"Split document into {len(chunks)} chunks.")
        
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}...")
            extraction = await self.extractor.extract(chunk)
            chunk_source_id = f"{source_id}#chunk_{i}"
            await self._merge_extraction(extraction, chunk_source_id)

    async def _merge_extraction(self, extraction: Dict[str, Any], source_id: str) -> None:
        """
        Merges extracted entities and relations into the GraphStore.
        """
        # Map names to actual Node IDs for relationship creation
        name_to_id = {}

        # 1. Process Entities using NodeMerger
        for ent_data in extraction.get("entities", []):
            name = ent_data.get("name")
            label = ent_data.get("label")
            if not name or not label:
                continue

            node = await self.merger.merge_or_create(
                name=name,
                label=label,
                properties=ent_data.get("properties", {}),
                source_id=source_id
            )
            name_to_id[name] = node.id

        # 2. Process Relations
        for rel_data in extraction.get("relations", []):
            source_name = rel_data.get("source")
            target_name = rel_data.get("target")
            relation = rel_data.get("relation")
            
            if not source_name or not target_name or not relation:
                continue
            
            source_id_node = name_to_id.get(source_name)
            target_id_node = name_to_id.get(target_name)
            
            # If the entities weren't in the same chunk's entity list, 
            # try finding them in the global store
            if not source_id_node:
                found = self.store.find_nodes_by_name(source_name)
                if found: source_id_node = found[0].id
            if not target_id_node:
                found = self.store.find_nodes_by_name(target_name)
                if found: target_id_node = found[0].id
                
            if source_id_node and target_id_node:
                edge = Edge(
                    source_node_id=source_id_node,
                    target_node_id=target_id_node,
                    relation=relation,
                    properties=rel_data.get("properties", {})
                )
                self.store.add_edge(edge)
