"""semantic.py — Find semantically similar notes.

Requires a running Qdrant instance and an embedding provider installed.
"""
from bfai.memory import semantic_search


def find_similar(query: str, top_k: int = 5, provider: str = "sentence-transformers"):
    """Search notes by meaning rather than exact keywords."""
    results = semantic_search(query, top_k=top_k, provider_name=provider)

    print(f'Semantic search for: "{query}"')
    print(f"Provider: {provider}")
    print(f"Results: {len(results)}\n")

    for i, r in enumerate(results, 1):
        print(f"{i}. [{r['score']:.4f}] {r['title']}")
        if r.get("metadata"):
            tags = r["metadata"].get("tags", [])
            if tags:
                print(f"   Tags: {', '.join(tags)}")
        print()


if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "machine learning"
    find_similar(query)