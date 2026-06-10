import asyncio
import logging
import sys
from graphmem.graph.store import GraphStore
from graphmem.graph.persistence import GraphPersistence
from graphmem.memory.ingester import DocumentIngester
from graphmem.core.config import settings

# Configure logging to see progress through the many chunks
# We'll use a more compact format to avoid flooding the console
logging.basicConfig(
    level=logging.INFO, 
    format='%(levelname)s: %(message)s',
    stream=sys.stdout
)

async def process_drake_bio():
    # 1. Initialize system
    store = GraphStore()
    persistence = GraphPersistence()
    ingester = DocumentIngester(store)
    
    file_path = "data/testfile.txt"
    
    print(f"--- STARTING INGESTION of {file_path} ---")
    
    try:
        # 2. Ingest the long file
        # The ingester will automatically chunk this based on the SimpleRecursiveSplitter
        await ingester.ingest(file_path, source_id="drake_wikipedia_bio")
        
        # 3. Save the resulting graph to SQLite
        persistence.save(store.graph)
        print(f"\n--- INGESTION COMPLETE ---")
        print(f"Graph saved to {settings.sqlite_path}")
        print(f"Total Nodes: {store.graph.number_of_nodes()}")
        print(f"Total Edges: {store.graph.number_of_edges()}")

        # 4. Analyze the central entity "Drake"
        print("\n--- ANALYZING CENTRAL ENTITY: DRAKE ---")
        # Try finding by common names
        potential_names = ["Drake", "Aubrey Drake Graham", "Aubrey Graham"]
        drake_node = None
        for name in potential_names:
            nodes = store.find_nodes_by_name(name)
            if nodes:
                drake_node = nodes[0]
                break
        
        if drake_node:
            print(f"Node Name: {drake_node.name}")
            print(f"Label: {drake_node.label}")
            print(f"Confidence Score: {drake_node.confidence:.2f}")
            print(f"Number of Sources: {len(drake_node.sources)}")
            
            neighbors = store.get_neighbors(drake_node.id)
            print(f"Total Relationships: {len(neighbors)}")
            
            # Print unique relationship types
            rels = set(n['edge'].relation for n in neighbors)
            print(f"Relationship types: {', '.join(rels)}")
            
            # Sample some interesting relations
            print("\nSample Relationships:")
            for nbr in neighbors[:10]:
                direction = "-->" if nbr['direction'] == 'outbound' else "<--"
                other = nbr['node'].name
                rel = nbr['edge'].relation
                print(f"  {drake_node.name} {direction} [{rel}] {direction} {other}")
        else:
            print("Drake node not found. Top 10 nodes by name:")
            all_nodes = sorted([n.name for _, n in store.graph.nodes(data='data')], key=len)
            for name in all_nodes[:10]:
                print(f"  - {name}")

    except Exception as e:
        print(f"An error occurred during ingestion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(process_drake_bio())
