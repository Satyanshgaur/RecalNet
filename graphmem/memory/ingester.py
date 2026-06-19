import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from uuid import uuid4

from graphmem.graph.models import Node, Edge, Episode
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
            episode = Episode(
                document_id=source_id,
                chunk_id=f"chunk_{i}",
                raw_text=chunk
            )
            self.store.add_episode(episode)
            
            extraction = await self.extractor.extract(chunk)
            await self._merge_extraction(extraction, episode)

    async def _merge_extraction(self, extraction: Dict[str, Any], episode: Episode) -> None:
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
                source_id=f"{episode.document_id}#{episode.chunk_id}"
            )
            name_to_id[name] = node.id
            self.store.add_node_mention(node.id, episode.id)

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
                # Track mentions for source and target node when a relation exists
                self.store.add_node_mention(source_id_node, episode.id)
                self.store.add_node_mention(target_id_node, episode.id)

                # Compute evidence reference character offsets
                evidence_text = rel_data.get("evidence", "")
                evidence_reference = None
                if evidence_text:
                    start_idx = episode.raw_text.find(evidence_text)
                    if start_idx == -1:
                        # Case insensitive check
                        start_idx = episode.raw_text.lower().find(evidence_text.lower())
                    
                    if start_idx != -1:
                        evidence_reference = {
                            "episode_id": episode.id,
                            "start_char": start_idx,
                            "end_char": start_idx + len(evidence_text)
                        }
                    else:
                        # Fallback to full raw text bounds
                        evidence_reference = {
                            "episode_id": episode.id,
                            "start_char": 0,
                            "end_char": len(episode.raw_text)
                        }

                # Check for existing identical edge (directional match)
                existing_edge = None
                if self.store.graph.has_edge(source_id_node, target_id_node):
                    edge_dict = self.store.graph.get_edge_data(source_id_node, target_id_node)
                    for edge_id, attr in edge_dict.items():
                        edge_obj: Edge = attr["data"]
                        if edge_obj.relation == relation:
                            existing_edge = edge_obj
                            break

                from graphmem.core.config import settings
                if existing_edge:
                    # Update supporting episodes and count
                    if episode.id not in existing_edge.supporting_episode_ids:
                        existing_edge.supporting_episode_ids.append(episode.id)
                        existing_edge.support_count += 1
                        # Corroboration boost for edge confidence
                        existing_edge.confidence = min(
                            existing_edge.confidence + settings.chunk_corroboration_bonus,
                            settings.max_confidence
                        )
                    # Merge properties, fact statement, and evidence reference
                    existing_edge.properties.update(rel_data.get("properties", {}))
                    if not existing_edge.fact and rel_data.get("fact"):
                        existing_edge.fact = rel_data.get("fact")
                    if not existing_edge.evidence_reference and evidence_reference:
                        existing_edge.evidence_reference = evidence_reference
                else:
                    # Create new edge
                    edge = Edge(
                        source_node_id=source_id_node,
                        target_node_id=target_id_node,
                        relation=relation,
                        confidence=settings.initial_confidence,
                        fact=rel_data.get("fact"),
                        supporting_episode_ids=[episode.id],
                        support_count=1,
                        evidence_reference=evidence_reference,
                        properties=rel_data.get("properties", {})
                    )
                    self.store.add_edge(edge)

