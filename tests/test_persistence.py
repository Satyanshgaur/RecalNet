import os
from pathlib import Path
from graphmem.graph.models import Node, Edge
from graphmem.graph.store import GraphStore
from graphmem.graph.persistence import GraphPersistence

def test_persistence():
    db_file = Path("test_graph.db")
    if db_file.exists():
        os.remove(db_file)
        
    persistence = GraphPersistence(db_path=db_file)
    store = GraphStore()

    print("Building test graph...")
    # 1. Create 4 Nodes
    elon = Node(name="Elon Musk", label="Person", properties={"born": 1971})
    spacex = Node(name="SpaceX", label="Organization")
    tesla = Node(name="Tesla", label="Organization")
    california = Node(name="California", label="Location")

    for n in [elon, spacex, tesla, california]:
        store.add_node(n)

    # 2. Create 4 Edges
    edges = [
        Edge(source_node_id=elon.id, target_node_id=spacex.id, relation="FOUNDED"),
        Edge(source_node_id=elon.id, target_node_id=tesla.id, relation="CEO_OF"),
        Edge(source_node_id=spacex.id, target_node_id=california.id, relation="LOCATED_IN"),
        Edge(source_node_id=tesla.id, target_node_id=california.id, relation="LOCATED_IN"),
    ]
    for e in edges:
        store.add_edge(e)

    print(f"Original graph: {store.graph.number_of_nodes()} nodes, {store.graph.number_of_edges()} edges.")
    
    # 3. Save
    print("Saving to SQLite...")
    persistence.save(store.graph)
    
    # 4. Clear memory and Reload
    print("Simulating restart and loading from SQLite...")
    persistence_new = GraphPersistence(db_path=db_file)
    reloaded_store = persistence_new.load()
    
    # 5. Assertions
    print("Verifying structure...")
    assert reloaded_store.graph.number_of_nodes() == 4, f"Expected 4 nodes, got {reloaded_store.graph.number_of_nodes()}"
    assert reloaded_store.graph.number_of_edges() == 4, f"Expected 4 edges, got {reloaded_store.graph.number_of_edges()}"
    
    # Check specific nodes
    spacex_nodes = reloaded_store.find_nodes_by_name("SpaceX")
    assert len(spacex_nodes) == 1
    assert spacex_nodes[0].label == "Organization"
    
    cali_nodes = reloaded_store.find_nodes_by_name("California")
    assert len(cali_nodes) == 1
    assert cali_nodes[0].label == "Location"
    
    elon_nodes = reloaded_store.find_nodes_by_name("Elon Musk")
    assert elon_nodes[0].properties["born"] == 1971
    
    # Check relationships
    elon_id = elon_nodes[0].id
    neighbors = reloaded_store.get_neighbors(elon_id)
    relations = [n["edge"].relation for n in neighbors]
    assert "FOUNDED" in relations
    assert "CEO_OF" in relations

    print("\nOK: PERSISTENCE VERIFIED!")
    print("OK: 4 nodes and 4 edges preserved.")
    print("OK: Metadata and properties preserved.")
    
    # Cleanup
    if db_file.exists():
        os.remove(db_file)

if __name__ == "__main__":
    test_persistence()
