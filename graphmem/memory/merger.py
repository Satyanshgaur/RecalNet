import logging
from typing import Optional, List, Dict, Any
from rapidfuzz import fuzz
from graphmem.graph.models import Node
from graphmem.graph.store import GraphStore

logger = logging.getLogger(__name__)

class NodeMerger:
    """
    Handles entity resolution and confidence scoring.
    """
    def __init__(self, store: GraphStore, similarity_threshold: float = 80.0):
        self.store = store
        self.similarity_threshold = similarity_threshold
        self.initial_confidence = 0.6
        self.corroboration_bonus = 0.1
        self.max_confidence = 0.95

    def find_best_match(self, name: str, label: str) -> Optional[Node]:
        """
        Finds the best existing node for a given name and label.
        Uses exact match first, then fuzzy matching.
        """
        # 1. Try exact normalized match first
        potential_nodes = self.store.find_nodes_by_label(label)
        
        normalized_name = name.lower().strip()
        
        # Exact match check
        for node in potential_nodes:
            if node.name.lower().strip() == normalized_name:
                return node
        
        # 2. Fuzzy match check
        best_score = 0
        best_node = None
        
        for node in potential_nodes:
            # WRatio is a weighted ratio that handles different lengths and common variations well
            score = fuzz.WRatio(normalized_name, node.name.lower().strip())
            logger.debug(f"Matching '{name}' with '{node.name}': Score {score}")
            if score > best_score and score >= self.similarity_threshold:
                best_score = score
                best_node = node
                
        if best_node:
            logger.info(f"Fuzzy merge: '{name}' matched with existing '{best_node.name}' (Score: {best_score})")
            
        return best_node

    def merge_or_create(self, name: str, label: str, properties: Dict[str, Any], source_id: str) -> Node:
        """
        Resolves an extracted entity to an existing node or creates a new one.
        Updates confidence based on the number of unique sources.
        """
        existing_node = self.find_best_match(name, label)
        
        if existing_node:
            # Update properties
            existing_node.properties.update(properties)
            
            # Update sources and confidence
            if source_id not in existing_node.sources:
                existing_node.sources.append(source_id)
                # Recalculate confidence: 0.6 + (extra_sources * 0.1)
                extra_sources = len(existing_node.sources) - 1
                new_confidence = min(self.initial_confidence + (extra_sources * self.corroboration_bonus), self.max_confidence)
                
                if new_confidence > existing_node.confidence:
                    logger.info(f"Confidence boost for '{existing_node.name}': {existing_node.confidence:.2f} -> {new_confidence:.2f}")
                    existing_node.confidence = new_confidence
            
            return existing_node
        else:
            # Create new node
            new_node = Node(
                name=name,
                label=label,
                properties=properties,
                sources=[source_id],
                confidence=self.initial_confidence
            )
            self.store.add_node(new_node)
            logger.info(f"Created new node: '{name}' ({label})")
            return new_node
