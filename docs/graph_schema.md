# Graph Schema Design

## 1. Nodes Table (`nodes`)
Stores entity information with full metadata.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (UUID) | Primary Key. Unique identifier for the node. |
| `label` | TEXT | Entity type (e.g., Person, Organization, Location). |
| `name` | TEXT | Human-readable name (indexed for fast lookup). |
| `properties` | TEXT (JSON) | Arbitrary metadata and attributes. |
| `confidence` | REAL | Float (0.0 - 1.0) representing extraction certainty. |
| `created_at` | TEXT (ISO) | Timestamp of first creation. |
| `updated_at` | TEXT (ISO) | Timestamp of last modification. |
| `sources` | TEXT (JSON) | List of source IDs (document/chunk IDs). |

## 2. Edges Table (`edges`)
Stores relationships between nodes.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (UUID) | Primary Key. Unique identifier for the edge. |
| `source_node_id` | TEXT (UUID) | Foreign Key -> `nodes.id`. |
| `target_node_id` | TEXT (UUID) | Foreign Key -> `nodes.id`. |
| `relation` | TEXT | Type of relationship (e.g., FOUNDED, CEO_OF). |
| `properties` | TEXT (JSON) | Arbitrary metadata (e.g., timestamps for temporal edges). |
| `confidence` | REAL | Float (0.0 - 1.0). |
| `created_at` | TEXT (ISO) | Timestamp of creation. |

## Indices
- `idx_nodes_name`: On `nodes.name` for fast retrieval.
- `idx_nodes_label`: On `nodes.label`.
- `idx_edges_source`: On `edges.source_node_id`.
- `idx_edges_target`: On `edges.target_node_id`.
