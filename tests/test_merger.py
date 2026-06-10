import asyncio
import logging
from graphmem.graph.store import GraphStore
from graphmem.memory.ingester import DocumentIngester

# Configure logging to see the merge decisions
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def test_fuzzy_merging():
    store = GraphStore()
    ingester = DocumentIngester(store)
    
    # Text with slightly different naming for the same entity
    text_1 = "OpenAI is an artificial intelligence research organization."
    text_2 = "Open AI was founded in 2015. OpenAI's mission is to ensure AGI benefits humanity."
    text_3 = "Open-AI receives funding from several sources."
    
    print("Ingesting Text 1...")
    await ingester.ingest(text_1, source_id="doc_1")
    
    print("\nIngesting Text 2 (corroboration and fuzzy match)...")
    await ingester.ingest(text_2, source_id="doc_2")
    
    print("\nIngesting Text 3 (another fuzzy match)...")
    await ingester.ingest(text_3, source_id="doc_3")
    
    print("\nFinal Graph Stats:")
    print(f"Nodes: {store.graph.number_of_nodes()}")
    
    openai_nodes = store.find_nodes_by_label("Organization")
    for node in openai_nodes:
        print(f"\nNode: {node.name}")
        print(f"  Confidence: {node.confidence:.2f}")
        print(f"  Sources: {node.sources}")
        
    # Validation
    # We expect one OpenAI node if fuzzy merging works
    assert len(openai_nodes) == 1, f"Expected 1 OpenAI node, found {len(openai_nodes)}"
    assert openai_nodes[0].confidence > 0.7, "Confidence should have increased"

if __name__ == "__main__":
    asyncio.run(test_fuzzy_merging())
