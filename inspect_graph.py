import asyncio
import logging
from graphmem.graph.store import GraphStore
from graphmem.graph.persistence import GraphPersistence
from graphmem.memory.ingester import DocumentIngester
from graphmem.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def run_inspection():
    # 1. Setup
    store = GraphStore()
    persistence = GraphPersistence()
    ingester = DocumentIngester(store)
    
    # 2. Ingest testfile.txt
    print("--- PHASE 1: INGESTION ---")
    await ingester.ingest("data/testfile.txt")
    
    # 3. Save to disk
    persistence.save(store.graph)
    print(f"Graph saved to {settings.sqlite_path}")

    # 4. Manual Inspection
    print("\n--- PHASE 2: GRAPH INSPECTION ---")
    print(f"Total Nodes: {store.graph.number_of_nodes()}")
    print(f"Total Edges: {store.graph.number_of_edges()}")

    # Check for SpaceX merging
    # We have "SpaceX", "Space Exploration Technologies Corp (SpaceX)", and "the company SpaceX"
    print("\nChecking Entity: SpaceX")
    spacex_variants = ["SpaceX", "Space Exploration Technologies Corp (SpaceX)"]
    for variant in spacex_variants:
        nodes = store.find_nodes_by_name(variant)
        for node in nodes:
            print(f"Found Node: '{node.name}' (Label: {node.label})")
            print(f"  Confidence: {node.confidence:.2f}")
            print(f"  Sources: {node.sources}")
            
            # Show relations
            neighbors = store.get_neighbors(node.id)
            for nbr in neighbors:
                direction = "->" if nbr['direction'] == 'outbound' else "<-"
                other_name = nbr['node'].name
                rel = nbr['edge'].relation
                print(f"  Relation: {node.name} {direction} [{rel}] {direction} {other_name}")

    # Check for Elon Musk merging
    print("\nChecking Entity: Elon Musk")
    musk_variants = ["Elon Musk", "Musk", "Elon Reeve Musk"]
    for variant in musk_variants:
        nodes = store.find_nodes_by_name(variant)
        for node in nodes:
            print(f"Found Node: '{node.name}'")
            print(f"  Confidence: {node.confidence:.2f}")

    # Check for Texas
    print("\nChecking Entity: Texas")
    texas = store.find_nodes_by_name("Texas")
    if texas:
        t = texas[0]
        neighbors = store.get_neighbors(t.id)
        print(f"Found Texas. Inbound connections: {[n['node'].name for n in neighbors if n['direction'] == 'inbound']}")

if __name__ == "__main__":
    asyncio.run(run_inspection())
