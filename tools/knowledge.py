"""search_knowledge agent capability: on-demand retrieval of technique writeups.

Keeps the system prompt small (it only carries the one-line index) while still
letting the agent pull up the full, concrete exploitation steps when it needs a
specific technique.
"""

from core.agent import Tool
from knowledge import search_techniques


def knowledge_tool(category: str) -> Tool:
    def handler(args: dict) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "Error: 'query' is required"
        results = search_techniques(category, query)
        if not results:
            return f"No technique matches {query!r}. Try fewer / more general keywords."
        parts = [r[:3500] for r in results[:2]]
        return "\n" + "\n\n---\n\n".join(parts) + "\n"

    return Tool(
        name="search_knowledge",
        description=(
            "Search the CTF technique knowledge base by keyword and return the full writeup "
            "of matching techniques (SQLi, deserialization, header forgery, SSRF, ...). Use it "
            "when you've identified a vulnerability class and need the concrete exploitation "
            "steps, instead of re-deriving them from scratch."
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
