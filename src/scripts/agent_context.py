"""agent_context.py — Get rich context for an AI agent.

This is the recommended way for AI agents to query the memory system.
"""
import json
from bfai.memory import retrieve, search


def get_agent_context(
    query: str,
    top_k: int = 5,
    max_hops: int = 2,
    include_backlinks: bool = True,
    use_hybrid: bool = True,
) -> dict:
    """
    Build a comprehensive context bundle for an AI agent.

    Returns a dict with:
    - query: the original query
    - direct_matches: notes that matched the query
    - supporting_knowledge: backlinks and graph neighbors
    - combined: flat list of all context items for easy formatting
    """
    context = retrieve(
        query=query,
        top_k=top_k,
        max_hops=max_hops,
        include_backlinks=include_backlinks,
        hybrid=use_hybrid,
    )

    direct = [c for c in context if c["source"] == "search"]
    supporting = [c for c in context if c["source"] != "search"]

    # Format as a prompt-friendly context string
    lines = ["# Knowledge Context", f"Query: {query}\n"]

    if direct:
        lines.append("## Direct Matches")
        for i, item in enumerate(direct, 1):
            lines.append(f"{i}. {item['title']}")

    if supporting:
        lines.append("\n## Supporting Knowledge")
        for item in supporting:
            source = item["source"].upper()
            lines.append(f"  [{source}] {item['title']}")
            if item.get("hop_depth"):
                lines[-1] += f" (hop {item['hop_depth']})"

    return {
        "query": query,
        "direct_matches": direct,
        "supporting_knowledge": supporting,
        "context_count": len(context),
        "formatted_context": "\n".join(lines),
    }


if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "robotics"
    ctx = get_agent_context(query)

    print(ctx["formatted_context"])
    print(f"\n--- {ctx['context_count']} total context items ---")

    # Output as JSON for programmatic use
    # print(json.dumps(ctx, indent=2))