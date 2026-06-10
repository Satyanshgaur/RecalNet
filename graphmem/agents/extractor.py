import json
import logging
import re
from typing import Any, Dict, List, Optional
from graphmem.core.ollama_client import OllamaClient
from graphmem.core.config import settings

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """
You are an expert knowledge graph extractor. Your task is to identify key entities and their relationships from the provided text.

### GUIDELINES:
1. **Entities**: Extract meaningful entities: Persons, Organizations, Locations, Concepts, Products, and Events. Skip incidental nouns.
2. **Relations**: Identify directional relationships (Source --Relation--> Target).
   - Ensure the direction is semantically correct (e.g., Elon Musk --FOUNDED--> SpaceX, NOT SpaceX --FOUNDED--> Elon Musk).
   - Use consistent, upper-case, snake_case verb forms (e.g., WORKS_AT, FOUNDED, LOCATED_IN, DEVELOPED, LEADS).
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
            return self.parse_extraction_output(raw_output)
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
