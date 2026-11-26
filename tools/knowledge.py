"""search_knowledge agent capability: on-demand retrieval of technique writeups.

Keeps the system prompt small (it only carries the one-line index) while still
letting the agent pull up the full, concrete exploitation steps when it needs a
specific technique.
"""

from core.agent import Tool
from knowledge import search_memories, search_techniques


def knowledge_tool(category: str) -> Tool:
    def handler(args: dict) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "Error: 'query' is required"
        parts: list[str] = []
        # 1) static technique cards for this category
        for r in search_techniques(category, query)[:2]:
            parts.append(r[:3500])
        # 2) accumulated memory pool (past solves, auto-saved)
        for m in search_memories(query, limit=3):
            content = (m.get("content") or "").strip()
            parts.append(f"[记忆 · {m.get('category')}] {m.get('title')}\n{content[:3000]}")
        if not parts:
            return f"No technique or past solve matches {query!r}. Try fewer / more general keywords."
        return "\n" + "\n\n---\n\n".join(parts) + "\n"

    return Tool(
        name="search_knowledge",
        description=(
            "Search the technique knowledge base (static cards + past-solve memory pool) by "
            "keyword and return the full writeups. Use it when you've identified a "
            "vulnerability class and need concrete exploitation steps — or to recall how a "
            "similar challenge was solved before."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords, e.g. 'SQL 注入过滤绕过', '反序列化', 'X-Forwarded-For'",
                }
            },
            "required": ["query"],
        },
        handler=handler,
    )
