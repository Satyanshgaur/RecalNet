import asyncio
from graphmem.agents.extractor import Extractor
from graphmem.graph.store import GraphStore
from graphmem.memory.merger import NodeMerger

async def test_canonical_ontology_and_resolution():
    extractor = Extractor()
    
    # 1. Test ontology label normalization
    assert extractor.normalize_label("School") == "EducationalInstitution"
    assert extractor.normalize_label("University") == "EducationalInstitution"
    assert extractor.normalize_label("Album") == "CreativeWork"
    assert extractor.normalize_label("Song") == "CreativeWork"
    assert extractor.normalize_label("Person") == "Person"
    assert extractor.normalize_label("RandomUnknownLabel") == "Other"
    
    # 2. Test upgrade to Multi-stage Entity Resolution with Dynamic Aliases
    store = GraphStore()
    merger = NodeMerger(store)
    
    # Add a Person node with canonical name Aubrey Drake Graham
    node = await merger.merge_or_create(
        name="Aubrey Drake Graham",
        label="Person",
        properties={},
        source_id="test_doc#chunk_0"
    )
    
    # Add a dynamic alias via a merge or fuzzy match / LLM adjudication simulation
    # Let's add it directly or trigger matching.
    # To avoid needing live LLM for simple unit tests, let's explicitly test find_best_match with an alias added to node.aliases:
    node.aliases.append("Aubrey Graham")
    
    # Resolving "Aubrey Graham" should now hit instant alias detection via node.aliases list
    match_alias_list = await merger.find_best_match("Aubrey Graham", "Person")
    assert match_alias_list is not None
    assert match_alias_list.name == "Aubrey Drake Graham"
    print("All framework checks PASSED successfully!")

if __name__ == "__main__":
    asyncio.run(test_canonical_ontology_and_resolution())
