import json
import logging
import re
from typing import Any, Dict, List, Optional
from rapidfuzz import fuzz
from graphmem.core.ollama_client import OllamaClient
from graphmem.core.config import settings

logger = logging.getLogger(__name__)

# Predefined standard relation types
ONTOLOGY_RELATIONS = {
    "ACTED_IN", "PRODUCED", "DIRECTED", "FOUNDED", "CEO_OF", "LOCATED_IN", 
    "WORKS_AT", "PARTNER_OF", "MEMBER_OF", "SUBSIDIARY_OF", "DEVELOPED", 
    "LEADS", "BORN_IN", "DIED_IN", "CITIZEN_OF", "AWARDED", "MARRIED_TO", 
    "CHILD_OF", "SIBLING_OF", "OTHER"
}

# Predefined synonym mapping for fast mapping
SYNONYM_MAPPINGS = {
    # LOCATED_IN
    "LIVES_IN": "LOCATED_IN",
    "HEADQUARTERED_IN": "LOCATED_IN",
    "HEADQUARTER": "LOCATED_IN",
    "HEADQUARTERED": "LOCATED_IN",
    "HQ_IN": "LOCATED_IN",
    "HQ": "LOCATED_IN",
    "BASED_IN": "LOCATED_IN",
    "OFFICE_IN": "LOCATED_IN",
    "RESIDES_IN": "LOCATED_IN",
    # WORKS_AT
    "EMPLOYED_BY": "WORKS_AT",
    "WORKS_FOR": "WORKS_AT",
    "STAFF_AT": "WORKS_AT",
    "ASSOCIATE_AT": "WORKS_AT",
    # CEO_OF
    "CHIEF_EXECUTIVE_OF": "CEO_OF",
    "RUNS": "CEO_OF",
    "PRESIDENT_OF": "CEO_OF",
    # FOUNDED
    "CREATOR_OF": "FOUNDED",
    "ESTABLISHED": "FOUNDED",
    "CREATED": "FOUNDED",
    "STARTED": "FOUNDED",
    # AWARDED
    "DECLARED_ARTIST_OF_THE_DECADE": "AWARDED",
    "WON": "AWARDED",
    "RECEIVED": "AWARDED",
    "NOMINATED_FOR": "AWARDED",
    "RECOGNIZED_WITH": "AWARDED",
    # ACTED_IN
    "STARRED_IN": "ACTED_IN",
    "PLAYED_IN": "ACTED_IN",
    # MARRIED_TO
    "SPOUSE_OF": "MARRIED_TO",
    "WIFE_OF": "MARRIED_TO",
    "HUSBAND_OF": "MARRIED_TO",
    # CHILD_OF
    "SON_OF": "CHILD_OF",
    "DAUGHTER_OF": "CHILD_OF",
    # SIBLING_OF
    "BROTHER_OF": "SIBLING_OF",
    "SISTER_OF": "SIBLING_OF",
}

EXTRACTION_SYSTEM_PROMPT = """
You are an expert knowledge graph extractor. Your task is to identify key entities and their relationships from the provided text.

### GUIDELINES:
1. **Entities**: Extract meaningful entities: Persons, Organizations, Locations, Concepts, Products, and Events. Skip incidental nouns.
2. **Relations**: Identify directional relationships (Source --Relation--> Target).
   - Ensure the direction is semantically correct (e.g., Elon Musk --FOUNDED--> SpaceX, NOT SpaceX --FOUNDED--> Elon Musk).
   - You MUST classify and map all relationships to one of the following standard RELATION ONTOLOGY TYPES (in uppercase snake_case):
     * ACTED_IN, PRODUCED, DIRECTED, FOUNDED, CEO_OF, LOCATED_IN, WORKS_AT, PARTNER_OF, MEMBER_OF, SUBSIDIARY_OF, DEVELOPED, LEADS, BORN_IN, DIED_IN, CITIZEN_OF, AWARDED, MARRIED_TO, CHILD_OF, SIBLING_OF
     * If no standard category fits, use OTHER.
3. **Properties**: Extract relevant properties (e.g., roles, dates, specific locations).
4. **Consistency**: Normalize entity names based on the text.
5. **No Hallucination**: ONLY extract information present in the text. Do NOT add entities from your training data that aren't mentioned.

### EXAMPLES:

**Input**: "SpaceX was founded by Elon Musk in 2002. It is headquartered in Hawthorne, California."
**Output**: 
{
  "entities": [
    {"name": "SpaceX", "label": "Organization", "properties": {"industry": "Aerospace"}},
    {"name": "Elon Musk", "label": "Person", "properties": {"role": "Founder"}},
    {"name": "Hawthorne", "label": "Location", "properties": {}},
    {"name": "California", "label": "Location", "properties": {}}
  ],
  "relations": [
    {"source": "Elon Musk", "target": "SpaceX", "relation": "FOUNDED", "properties": {"year": 2002}},
    {"source": "SpaceX", "target": "Hawthorne", "relation": "LOCATED_IN", "properties": {}},
    {"source": "Hawthorne", "target": "California", "relation": "LOCATED_IN", "properties": {}}
  ]
}
"""

class Extractor:
    """
    Handles the extraction of entities and relations from text using an LLM.
    """
    
    def __init__(self, client: Optional[OllamaClient] = None):
        self.client = client or OllamaClient()

    def normalize_relation(self, relation: str) -> tuple[str, Dict[str, Any]]:
        """
        Normalizes a relation string to the closest ontology relation.
        Returns (normalized_relation, extra_properties) where original relation is stored
        in properties if it was normalized/changed.
        """
        cleaned = relation.strip().upper().replace(" ", "_").replace("-", "_")
        
        # 1. Exact match
        if cleaned in ONTOLOGY_RELATIONS:
            return cleaned, {}
            
        # 2. Synonym mapping
        if cleaned in SYNONYM_MAPPINGS:
            norm = SYNONYM_MAPPINGS[cleaned]
            return norm, {"original_relation": relation}
            
        # 3. Fuzzy string matching mapping (using rapidfuzz)
        best_score = 0.0
        best_match = None
        for ont_rel in ONTOLOGY_RELATIONS:
            if ont_rel == "OTHER":
                continue
            # Check similarity
            score = fuzz.ratio(cleaned, ont_rel)
            if score > best_score and score >= 75.0:
                best_score = score
                best_match = ont_rel
                
        if best_match:
            return best_match, {"original_relation": relation}
            
        # 4. Fallback to OTHER
        return "OTHER", {"original_relation": relation}

    async def extract(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract entities and relations from a text chunk.
        """
        prompt = f"Text to extract from:\n\n{text}\n\nReturn the JSON object:"
        
        try:
            response = await self.client.generate(
                prompt, 
                system=EXTRACTION_SYSTEM_PROMPT,
                format="json"
            )
            raw_output = response.get("response", "")
            result = self.parse_extraction_output(raw_output)
            
            # Post-process relations to normalize them
            if "relations" in result:
                for rel_data in result["relations"]:
                    rel_name = rel_data.get("relation")
                    if rel_name:
                        norm_rel, extra_props = self.normalize_relation(rel_name)
                        rel_data["relation"] = norm_rel
                        if extra_props:
                            if "properties" not in rel_data:
                                rel_data["properties"] = {}
                            rel_data["properties"].update(extra_props)
                            
            return result
        except Exception as e:
            logger.error(f"Extraction failed: {str(e)}")
            return {"entities": [], "relations": []}

    def parse_extraction_output(self, raw_text: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Robustly parse the LLM's output into a dictionary.
        Tries direct JSON loading, then regex extraction from code blocks.
        """
        raw_text = raw_text.strip()
        
        # 1. Try direct parse
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass
            
        # 2. Try to extract from markdown code blocks
        json_match = re.search(r"```json\s*(.*?)\s*```", raw_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 3. Try to find anything that looks like a JSON object
        json_match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        logger.warning(f"Failed to parse extraction output. Raw text length: {len(raw_text)}")
        return {"entities": [], "relations": []}
