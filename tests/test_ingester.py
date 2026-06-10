import asyncio
import logging
from graphmem.graph.store import GraphStore
from graphmem.memory.ingester import DocumentIngester

# Configure logging to see the progress
logging.basicConfig(level=logging.INFO)

async def test_ingester():
    store = GraphStore()
    ingester = DocumentIngester(store)
    
    test_text = (
        "SpaceX, the aerospace company founded by Elon Musk in 2002, is revolutionizing space travel. "
        "The company is famous for its Falcon 9 rockets. "
        "Elon Musk also leads Tesla, which produces electric vehicles in California. "
        "SpaceX has major operations in Texas and Florida as well."
    )
    
    print("Starting ingestion...")
    await ingester.ingest(test_text, source_id="test_doc_1")
    
    print("\nIngestion Complete. Graph Stats:")
    print(f"Nodes: {store.graph.number_of_nodes()}")
    print(f"Edges: {store.graph.number_of_edges()}")
    
    # Verify entity merging
    elon_nodes = store.find_nodes_by_name("Elon Musk")
    print(f"\nFound {len(elon_nodes)} node(s) named 'Elon Musk'.")
    if elon_nodes:
        elon = elon_nodes[0]
        neighbors = store.get_neighbors(elon.id)
        print(f"Elon's relationships: {[n['edge'].relation for n in neighbors]}")
        print(f"Elon's sources: {elon.sources}")

    # Check for Texas/Florida
    texas = store.find_nodes_by_name("Texas")
    if texas:
        print(f"✓ Found node for 'Texas'.")

if __name__ == "__main__":
    asyncio.run(test_ingester())
