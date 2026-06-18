import asyncio
import logging
import sys
from graphmem.graph.store import GraphStore
from graphmem.graph.persistence import GraphPersistence
from graphmem.memory.ingester import DocumentIngester
from graphmem.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(levelname)s: %(message)s',
    stream=sys.stdout
)

async def test_drake_partial():
    # 1. Initialize system
    store = GraphStore()
    persistence = GraphPersistence()
    ingester = DocumentIngester(store)
    
    file_path = "data/testfile.txt"
    
    print(f"--- STARTING PARTIAL INGESTION of {file_path} ---")
    
    try:
        # Read only the first 5000 characters (approx 2-3 chunks)
        with open(file_path, "r", encoding="utf-8") as f:
            full_text = f.read()
            partial_text = full_text[:5000]
            
        print(f"Read {len(partial_text)} characters from {file_path}")
        
        # 2. Ingest the text
        await ingester.ingest(partial_text, source_id="drake_partial")
        
        # 3. Analyze the graph
        print(f"\n--- INGESTION COMPLETE ---")
        print(f"Total Nodes: {store.graph.number_of_nodes()}")
        print(f"Total Edges: {store.graph.number_of_edges()}")

        print("\n--- NODES (Top 20) ---")
        all_nodes = list(store.graph.nodes(data='data'))
        for _, node in all_nodes[:20]:
            print(f"- {node.name} ({node.label}) [Conf: {node.confidence:.2f}]")

        print("\n--- EDGES (Top 20) ---")
        all_edges = list(store.graph.edges(data='data'))
        for u, v, edge in all_edges[:20]:
            u_node = store.get_node(u)
            v_node = store.get_node(v)
            print(f"- {u_node.name} --[{edge.relation}]--> {v_node.name}")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_drake_partial())
