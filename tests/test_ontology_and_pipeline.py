import asyncio
import logging
from graphmem.agents.extractor import Extractor
from graphmem.graph.store import GraphStore
from graphmem.memory.merger import NodeMerger
from graphmem.memory.ingester import DocumentIngester

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def run_ontology_tests():
    extractor = Extractor()
    
    print("--- 1. Testing Relation Ontology Normalization ---")
    # Test mapping of DECLARED_ARTIST_OF_THE_DECADE
    rel, props = extractor.normalize_relation("DECLARED_ARTIST_OF_THE_DECADE")
    print(f"DECLARED_ARTIST_OF_THE_DECADE mapped to: {rel}")
    print(f"Properties: {props}")
    assert rel == "AWARDED"
    assert props.get("original_relation") == "DECLARED_ARTIST_OF_THE_DECADE"
    
    # Test synonym mapping
    rel2, props2 = extractor.normalize_relation("LIVES_IN")
    print(f"LIVES_IN mapped to: {rel2}")
    assert rel2 == "LOCATED_IN"
    
    # Test fuzzy mapping
    rel3, props3 = extractor.normalize_relation("HEADQUARTER")
    print(f"HEADQUARTER mapped to: {rel3}")
    assert rel3 == "LOCATED_IN"
    
    # Test fallback to OTHER
    rel4, props4 = extractor.normalize_relation("INVENTED_RELATION_X")
    print(f"INVENTED_RELATION_X mapped to: {rel4}")
    assert rel4 == "OTHER"
    assert props4.get("original_relation") == "INVENTED_RELATION_X"
    print("OK: Relation normalization tests passed.")
    
    print("\n--- 2. Testing Stop Word Stripping ---")
    store = GraphStore()
    merger = NodeMerger(store)
    
    stripped_univ = merger._strip_stop_words("The University of California")
    print(f"'The University of California' -> '{stripped_univ}'")
    assert stripped_univ == "university california"
    
    stripped_nyc = merger._strip_stop_words("New York City")
    print(f"'New York City' -> '{stripped_nyc}'")
    assert stripped_nyc == "new york"
    
    stripped_okc = merger._strip_stop_words("Oklahoma City")
    print(f"'Oklahoma City' -> '{stripped_okc}'")
    assert stripped_okc == "oklahoma"
    print("OK: Stop word stripping tests passed.")
    
    print("\n--- 3. Testing Semantic Entity Deduplication (NYC vs Oklahoma City) ---")
    # We will manually merge them using the NodeMerger to see if they get resolved correctly
    # First create New York City
    node_nyc = await merger.merge_or_create("New York City", "Location", {}, "doc_1#chunk_0")
    print(f"Created/merged: {node_nyc.name}")
    
    # Try to merge Oklahoma City
    node_okc = await merger.merge_or_create("Oklahoma City", "Location", {}, "doc_2#chunk_0")
    print(f"Created/merged: {node_okc.name}")
    
    # Since New York City strips to "new york" and Oklahoma City strips to "oklahoma",
    # their similarity score should be low and they should NOT be merged.
    assert node_nyc.id != node_okc.id
    print("OK: New York City and Oklahoma City were correctly NOT merged.")

    print("\n--- 4. Testing LLM Adjudication (Apple vs Pineapple) ---")
    # Apple vs Pineapple has a high WRatio score (90.0) so it hits the borderline check
    node_apple = await merger.merge_or_create("Apple", "Concept", {}, "doc_1#chunk_0")
    node_pineapple = await merger.merge_or_create("Pineapple", "Concept", {}, "doc_2#chunk_0")
    
    assert node_apple.id != node_pineapple.id
    print("OK: Apple and Pineapple were correctly NOT merged.")
    
    print("\nALL SYSTEM PIPELINE AND ONTOLOGY TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(run_ontology_tests())
