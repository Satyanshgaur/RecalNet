from graphmem.graph.models import Node, Edge
from graphmem.graph.store import GraphStore

def test_manual_graph():
    store = GraphStore()

    # 1. Create Nodes
    elon = Node(name="Elon Musk", label="Person")
    spacex = Node(name="SpaceX", label="Company")
    tesla = Node(name="Tesla", label="Company")
    california = Node(name="California", label="Location")

    nodes = [elon, spacex, tesla, california]
    for n in nodes:
        store.add_node(n)
    
    print(f"Added {len(nodes)} nodes.")

    # 2. Create Edges
    edges = [
        Edge(source_node_id=elon.id, target_node_id=spacex.id, relation="FOUNDED"),
        Edge(source_node_id=elon.id, target_node_id=tesla.id, relation="CEO_OF"),
        Edge(source_node_id=spacex.id, target_node_id=california.id, relation="LOCATED_IN"),
        Edge(source_node_id=tesla.id, target_node_id=california.id, relation="LOCATED_IN"),
    ]

    for e in edges:
        store.add_edge(e)
    
    print(f"Added {len(edges)} edges.")

    # 3. Verification
    # Find nodes by name
    found_elon = store.find_nodes_by_name("Elon Musk")
    assert len(found_elon) == 1
    assert found_elon[0].label == "Person"
    print("OK: find_nodes_by_name verified.")

    # Find nodes by label
    companies = store.find_nodes_by_label("Company")
    assert len(companies) == 2
    print(f"OK: find_nodes_by_label verified ({len(companies)} companies).")

    # Get neighbors for Elon Musk
    elon_neighbors = store.get_neighbors(elon.id)
    assert len(elon_neighbors) == 2
    relations = [n["edge"].relation for n in elon_neighbors]
    assert "FOUNDED" in relations
    assert "CEO_OF" in relations
    print(f"OK: get_neighbors verified for {elon.name}: {[r for r in relations]}")

    # Get neighbors for California (Inbound)
    ca_neighbors = store.get_neighbors(california.id)
    assert len(ca_neighbors) == 2
    inbound_names = [n["node"].name for n in ca_neighbors if n["direction"] == "inbound"]
    assert "SpaceX" in inbound_names
    assert "Tesla" in inbound_names
    print(f"OK: Inbound neighbors verified for {california.name}: {inbound_names}")

    print("\nALL MANUAL GRAPH TESTS PASSED!")

if __name__ == "__main__":
    test_manual_graph()
