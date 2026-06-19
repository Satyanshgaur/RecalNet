import os
from pathlib import Path
from uuid import UUID
from graphmem.graph.models import Node, Edge, Episode
from graphmem.graph.store import GraphStore
from graphmem.graph.persistence import GraphPersistence

def test_persistence():
    db_file = Path("test_graph.db")
    if db_file.exists():
        os.remove(db_file)
        
    persistence = GraphPersistence(db_path=db_file)
    store = GraphStore()

    print("Building test graph...")
    # 1. Create Episode
    ep = Episode(
        document_id="doc_1",
        chunk_id="chunk_0",
        raw_text="Elon Musk founded SpaceX in 2002. He is also the CEO of Tesla, based in California."
    )
    store.add_episode(ep)

    # 2. Create 4 Nodes
    elon = Node(name="Elon Musk", label="Person", properties={"born": 1971})
    spacex = Node(name="SpaceX", label="Organization")
    tesla = Node(name="Tesla", label="Organization")
    california = Node(name="California", label="Location")

    for n in [elon, spacex, tesla, california]:
        store.add_node(n)
        store.add_node_mention(n.id, ep.id)

    # 3. Create 4 Edges with enriched facts and evidence refs
    edges = [
        Edge(
            source_node_id=elon.id,
            target_node_id=spacex.id,
            relation="FOUNDED",
            fact="Elon Musk founded SpaceX",
            supporting_episode_ids=[ep.id],
            support_count=1,
            evidence_reference={"episode_id": ep.id, "start_char": 0, "end_char": 32}
        ),
        Edge(
            source_node_id=elon.id,
            target_node_id=tesla.id,
            relation="CEO_OF",
            fact="Elon Musk is the CEO of Tesla",
            supporting_episode_ids=[ep.id],
            support_count=1
        ),
        Edge(
            source_node_id=spacex.id,
            target_node_id=california.id,
            relation="LOCATED_IN",
            supporting_episode_ids=[ep.id],
            support_count=1
        ),
        Edge(
            source_node_id=tesla.id,
            target_node_id=california.id,
            relation="LOCATED_IN",
            supporting_episode_ids=[ep.id],
            support_count=1
        ),
    ]
    for e in edges:
        store.add_edge(e)

    print(f"Original graph: {store.graph.number_of_nodes()} nodes, {store.graph.number_of_edges()} edges, {len(store.episodes)} episodes.")
    
    # 4. Save
    print("Saving to SQLite...")
    persistence.save(store.graph)
    
    # 5. Clear memory and Reload
    print("Simulating restart and loading from SQLite...")
    persistence_new = GraphPersistence(db_path=db_file)
    reloaded_store = persistence_new.load()
    
    # 6. Assertions
    print("Verifying structure...")
    assert reloaded_store.graph.number_of_nodes() == 4, f"Expected 4 nodes, got {reloaded_store.graph.number_of_nodes()}"
    assert reloaded_store.graph.number_of_edges() == 4, f"Expected 4 edges, got {reloaded_store.graph.number_of_edges()}"
    assert len(reloaded_store.episodes) == 1, f"Expected 1 episode, got {len(reloaded_store.episodes)}"
    
    # Check loaded episode
    loaded_ep = reloaded_store.get_episode(ep.id)
    assert loaded_ep is not None
    assert loaded_ep.document_id == "doc_1"
    assert loaded_ep.chunk_id == "chunk_0"
    assert "Elon Musk founded SpaceX" in loaded_ep.raw_text
    
    # Check specific nodes
    spacex_nodes = reloaded_store.find_nodes_by_name("SpaceX")
    assert len(spacex_nodes) == 1
    assert spacex_nodes[0].label == "Organization"
    
    cali_nodes = reloaded_store.find_nodes_by_name("California")
    assert len(cali_nodes) == 1
    assert cali_nodes[0].label == "Location"
    
    elon_nodes = reloaded_store.find_nodes_by_name("Elon Musk")
    assert elon_nodes[0].properties["born"] == 1971
    
    # Check node mentions
    explanations = reloaded_store.explain_node(elon_nodes[0].id)
    assert len(explanations["mentioned_in"]) == 1
    assert explanations["mentioned_in"][0].id == ep.id

    # Check relationships and explainability
    elon_id = elon_nodes[0].id
    neighbors = reloaded_store.get_neighbors(elon_id)
    
    # Find FOUNDED edge
    founded_edge = None
    for n in neighbors:
        if n["edge"].relation == "FOUNDED":
            founded_edge = n["edge"]
            break
            
    assert founded_edge is not None
    assert founded_edge.fact == "Elon Musk founded SpaceX"
    assert founded_edge.support_count == 1
    assert founded_edge.supporting_episode_ids == [ep.id]
    assert founded_edge.evidence_reference is not None
    assert founded_edge.evidence_reference["start_char"] == 0
    assert founded_edge.evidence_reference["end_char"] == 32

    # Explain edge
    edge_explanation = reloaded_store.explain_edge(founded_edge.id)
    assert edge_explanation["fact"] == "Elon Musk founded SpaceX"
    assert len(edge_explanation["supporting_episodes"]) == 1
    assert edge_explanation["supporting_episodes"][0].id == ep.id

    print("\nOK: PERSISTENCE VERIFIED!")
    print("OK: 4 nodes, 4 edges, 1 episode and mentions preserved.")
    
    # Cleanup
    if db_file.exists():
        os.remove(db_file)

if __name__ == "__main__":
    test_persistence()

