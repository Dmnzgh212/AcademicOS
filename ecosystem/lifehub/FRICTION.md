# First ecosystem friction record

| Observation | Evidence | Classification / next step |
| --- | --- | --- |
| Domain schemas and extension points fit existing catalog/records contracts | Three distinct schemas, arbitrary points discovered and rendered by independent Shells | Ecosystem contracts; no Core change |
| Read and descriptor grants remain independent from installation and ingestion | All three denied before grants and after revoke; incoming descriptor grants removed on uninstall | Existing mechanism works |
| Guest cannot fetch or parse local source files through ambient authority | Wasm imports unchanged; explicit operator companion performs local source selection | Alpha boundary; true sandboxed connector collection not demonstrated |
| Operator ingress uses trusted storage API | Explicit approve-ingest, operator provenance; providers request no write authority | Operator integration, not guest authority; do not claim self-contained sandboxed connectors |
| CSV/RSS inputs require explicit supported-format checks | Date offset, columns, XML declarations/root/row/byte limits tested | Domain adapter/DX; no Core change |
| Generic record reader returns byte count, not domain analysis | Guests read real normalized records; parser/domain logic stays in operator companion | First-pass scope; richer guest domain computation still needs real-use evidence |
| Shell presentation is generic | Both metadata and record consumers accept arbitrary domain contracts | Specialized domain views belong to ecosystem Shells |
| Per-source updates deduplicate identical content but do not implement record deletion/replacement | Operator uses content-derived keys and current append storage | Evaluate with live export/feed updates before proposing lifecycle changes |
| Read exports show latest eight records | Existing contract default; current fixtures fit | DX/live-data paging evidence needed, not automatic v0.2 rewrite |
| Academic and RSS runs use format-correct synthetic fixtures | No user-selected source exports supplied or private source sessions accessed | Live user acceptance pending; do not mark next phase complete |

No frozen Core file was modified. No finding here justifies restarting PersonIR.
Next run user-selected academic and RSS files, inspect useful output and update
this ledger before the post-ecosystem platform audit. Keep known Alpha limits.
