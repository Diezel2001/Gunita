"""explorer.py — Interactive CLI for searching and browsing notes."""
from bfai.memory import search, backlinks, related, retrieve


def main():
    print("BFAI Knowledge Explorer")
    print("Commands: search <q> | retrieve <q> | backlinks <id> | related <id> | quit\n")

    while True:
        try:
            line = input("bfai> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not line:
            continue
        if line == "quit":
            break

        parts = line.split(maxsplit=1)
        cmd = parts[0]
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "search":
            results = search(arg, limit=10)
            for r in results:
                print(f"  [{r['combined_score']:.3f}] {r['title']}")
            if not results:
                print("  (no results)")

        elif cmd == "retrieve":
            ctx = retrieve(arg, top_k=5, max_hops=2)
            for item in ctx:
                tag = f"[{item['source']}]"
                hop = item.get("hop_depth", "")
                print(f"  {tag:>10} {item['title']} {hop}")
            if not ctx:
                print("  (no results)")

        elif cmd == "backlinks":
            bl = backlinks(arg)
            for b in bl:
                print(f"  ← {b['related_title']} ({b['relationship_type']})")
            if not bl:
                print("  (no backlinks)")

        elif cmd == "related":
            rel = related(arg, direction="both")
            for r in rel:
                print(f"  ↔ {r['related_title']} [{r['relationship_type']}]")
            if not rel:
                print("  (no related notes)")

        else:
            print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()