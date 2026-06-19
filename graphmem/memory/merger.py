import logging
import re
from typing import Optional, List, Dict, Any
from rapidfuzz import fuzz
from graphmem.graph.models import Node
from graphmem.graph.store import GraphStore
from graphmem.core.config import settings
from graphmem.core.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

GLOBAL_ALIASES = {}

class NodeMerger:
    """
    Handles entity resolution and confidence scoring.
    """
    def __init__(self, store: GraphStore, client: Optional[OllamaClient] = None):
        self.store = store
        self.client = client or OllamaClient()
        self.similarity_threshold = settings.similarity_threshold
        self.exact_similarity_threshold = settings.exact_similarity_threshold
        self.initial_confidence = settings.initial_confidence
        self.doc_corroboration_bonus = settings.doc_corroboration_bonus
        self.chunk_corroboration_bonus = settings.chunk_corroboration_bonus
        self.max_confidence = settings.max_confidence
        self.use_llm_disambiguation = settings.use_llm_disambiguation

    def _strip_stop_words(self, name: str) -> str:
        """
        Strips common stop words and generic entity indicators to compare core names.
        e.g., 'The University of California' -> 'university california'
        e.g., 'New York City' -> 'new york'
        """
        words = re.findall(r'\b\w+\b', name.lower())
        stop_words = {
            "the", "of", "and", "a", "an", "in", "on", "at", "for", "with", "by", "to", 
            "co", "corp", "inc", "ltd", "gmbh", "limited", "company", "organization", "group", "city"
        }
        filtered_words = [w for w in words if w not in stop_words]
        return " ".join(filtered_words) if filtered_words else name.lower()

    def get_compatible_labels(self, label: str) -> List[str]:
        """Get list of labels that are semantically compatible with the target label."""
        groups = [
            {"Organization", "EducationalInstitution", "Location"},
            {"CreativeWork", "Product", "Other"},
        ]
        compat = {label}
        for g in groups:
            if label in g:
                compat.update(g)
        return list(compat)

    def promote_label(self, label_a: str, label_b: str) -> str:
        """Promotes the entity's label to the more specific canonical label."""
        preference = [
            "Other",
            "Location",
            "Organization",
            "EducationalInstitution",
            "Product",
            "CreativeWork",
            "Person",
            "Event",
            "Document",
            "Achievement"
        ]
        try:
            idx_a = preference.index(label_a)
        except ValueError:
            idx_a = -1
        try:
            idx_b = preference.index(label_b)
        except ValueError:
            idx_b = -1
            
        return label_a if idx_a >= idx_b else label_b

    async def find_best_match(self, name: str, label: str) -> Optional[Node]:
        """
        Finds the best existing node for a given name and label.
        Pipeline: Label Compatibility -> Alias Detection -> Fuzzy -> LLM Adjudication
        """
        # 1. Label Compatibility (Only compare against matching or compatible labels)
        compatible_labels = self.get_compatible_labels(label)
        potential_nodes = []
        for cl in compatible_labels:
            potential_nodes.extend(self.store.find_nodes_by_label(cl))
        
        normalized_name = name.lower().strip()
        
        # Look up canonical name from GLOBAL_ALIASES if any
        lookup_name = name.strip()
        if lookup_name in GLOBAL_ALIASES:
            lookup_name = GLOBAL_ALIASES[lookup_name]
        normalized_lookup = lookup_name.lower().strip()
        
        # 2. Alias Detection (Check name, aliases, or global canonical mapping)
        for node in potential_nodes:
            if node.name.lower().strip() == normalized_lookup:
                return node
            if node.name.lower().strip() == normalized_name:
                return node
            # Check dynamic aliases list stored on node
            for alias in getattr(node, "aliases", []):
                if alias.lower().strip() == normalized_name:
                    logger.info(f"Alias Detection hit: '{name}' instantly resolved to existing node '{node.name}' via aliases list.")
                    return node
        
        # 3. Fuzzy match check
        stripped_name = self._strip_stop_words(lookup_name)
        best_score = 0.0
        best_node = None
        
        for node in potential_nodes:
            stripped_node_name = self._strip_stop_words(node.name)
            score = fuzz.WRatio(stripped_name, stripped_node_name)
            logger.debug(f"Matching '{lookup_name}' with '{node.name}': Score {score}")
            if score > best_score and score >= self.similarity_threshold:
                best_score = score
                best_node = node
                
        if best_node:
            # Safe match above the exact similarity threshold
            if best_score >= self.exact_similarity_threshold:
                logger.info(f"Fuzzy merge (Safe): '{name}' matched with existing '{best_node.name}' (Score: {best_score})")
                if name not in best_node.aliases and name != best_node.name:
                    best_node.aliases.append(name)
                return best_node
            
            # Borderline match: run LLM adjudication
            if self.use_llm_disambiguation:
                logger.info(f"Fuzzy merge (Borderline): '{name}' matched with '{best_node.name}' (Score: {best_score}). Running LLM adjudication...")
                prompt = f"""Compare these two entity names of the same label and decide if they refer to the same real-world entity.

Entity A:
{name}

Entity B:
{best_node.name}

If they represent the same real-world entity (even with minor spelling variations, spacing, punctuation, or abbreviation differences, such as 'OpenAI' and 'Open AI'), respond with 'SAME'.
If they are distinct real-world entities (such as 'New York City' and 'Oklahoma City', or 'Apple' and 'Pineapple'), respond with 'DIFFERENT'.

Respond with ONLY the word 'SAME' or 'DIFFERENT'. Do not include any explanation or extra text."""
                try:
                    response = await self.client.generate(prompt)
                    output = response.get("response", "").strip().upper()
                    is_same = "SAME" in output and "DIFFERENT" not in output
                    logger.info(f"LLM Adjudication result for '{name}' vs '{best_node.name}': {output} (Parsed: same={is_same})")
                    if is_same:
                        if name not in best_node.aliases and name != best_node.name:
                            best_node.aliases.append(name)
                        return best_node
                except Exception as e:
                    logger.error(f"LLM adjudication failed for '{name}' vs '{best_node.name}': {str(e)}")
            else:
                logger.info(f"Fuzzy merge (Borderline): '{name}' matched with '{best_node.name}' (Score: {best_score}) but LLM adjudication is disabled.")
            
        return None

    async def merge_or_create(self, name: str, label: str, properties: Dict[str, Any], source_id: str) -> Node:
        """
        Resolves an extracted entity to an existing node or creates a new one.
        Updates confidence based on the number of unique documents and chunks.
        """
        existing_node = await self.find_best_match(name, label)
        
        if existing_node:
            # Promote label if necessary (e.g., Organization -> EducationalInstitution)
            promoted_label = self.promote_label(existing_node.label, label)
            if promoted_label != existing_node.label:
                logger.info(f"Promoting label of node '{existing_node.name}': {existing_node.label} -> {promoted_label}")
                existing_node.label = promoted_label
                # Also update in NetworkX graph node attributes
                self.store.graph.nodes[existing_node.id]["label"] = promoted_label
            
            # Update properties
            existing_node.properties.update(properties)
            
            # Update sources and confidence
            if source_id not in existing_node.sources:
                existing_node.sources.append(source_id)
                
                # Count unique documents and unique chunks
                unique_docs = set()
                for src in existing_node.sources:
                    if "#chunk_" in src:
                        doc_id = src.split("#chunk_")[0]
                    else:
                        doc_id = src
                    unique_docs.add(doc_id)
                
                num_docs = len(unique_docs)
                num_chunks = len(existing_node.sources)
                
                extra_docs = max(0, num_docs - 1)
                extra_chunks = max(0, num_chunks - num_docs)
                
                new_confidence = min(
                    self.initial_confidence + 
                    (extra_docs * self.doc_corroboration_bonus) + 
                    (extra_chunks * self.chunk_corroboration_bonus),
                    self.max_confidence
                )
                
                if new_confidence > existing_node.confidence:
                    logger.info(f"Confidence boost for '{existing_node.name}': {existing_node.confidence:.2f} -> {new_confidence:.2f} (Docs: {num_docs}, Chunks: {num_chunks})")
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

