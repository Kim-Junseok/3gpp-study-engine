# 3GPP Study Engine

Build a general, provenance-first system for studying 3GPP RAN meeting material.

- Correctness and source traceability matter more than breadth.
- Never fabricate missing 3GPP metadata; preserve unknowns as null.
- Never conflate a company proposal or observation with a meeting agreement.
- Keep discovery time separate from byte-retrieval time; preserve downloaded raw source material unchanged with URL, identity, retrieval time, and checksum.
- Prefer small, incremental changes and run the tests after each change.
- Update architecture documents when architectural decisions change.
- Do not add vector search, embeddings, or LLM/agent frameworks unless explicitly requested.
