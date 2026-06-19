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
        
        # Verify explain_node
        node_explanation = store.explain_node(elon.id)
        print(f"Elon Musk mentioned in {len(node_explanation['mentioned_in'])} episodes:")
        for ep in node_explanation["mentioned_in"]:
            print(f"  - Episode ID: {ep.id} ({ep.document_id}#{ep.chunk_id})")
        
        # Verify explain_edge
        for nbr in neighbors:
            edge = nbr["edge"]
            edge_explanation = store.explain_edge(edge.id)
            print(f"\nExplain Edge ({elon.name} -{edge.relation}-> {nbr['node'].name}):")
            print(f"  Fact: {edge_explanation['fact']}")
            print(f"  Confidence: {edge_explanation['confidence']:.2f}")
            print(f"  Support Count: {edge.support_count}")
            if edge.evidence_reference:
                ref = edge.evidence_reference
                print(f"  Evidence Reference: Episode {ref['episode_id']} (chars {ref['start_char']}-{ref['end_char']})")
                evidence_text = store.get_episode(ref['episode_id']).raw_text[ref['start_char']:ref['end_char']]
                print(f"    Text: \"{evidence_text}\"")

    # Check for Texas/Florida
    texas = store.find_nodes_by_name("Texas")
    if texas:
        print(f"✓ Found node for 'Texas'.")

if __name__ == "__main__":
    asyncio.run(test_ingester())

