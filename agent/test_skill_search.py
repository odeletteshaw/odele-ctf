"""Skill-search relevance: idf-weighted field matching with a distinctive-hit gate.

Regression for the EasySSTI run, where a generic "python/web" body match pulled a
JS-deobfuscation card to the top for every SSTI query, drowning the "no coverage"
signal so the harvester never wrote (or correctly skipped) a card.

The gate: a query token qualifies a result only when it is DISTINCTIVE (not in half
the cards), wherever it lands — so generic words never qualify a card, but a rare term
surfaces coverage even when it only appears in a card's body.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import skills  # noqa: E402


def card(sid, name, description, tags):
    return {"id": sid, "name": name, "description": description, "tags": tags,
            "kind": "reference", "path": None}


def setup(cards_and_bodies):
    items = [card(*c) for c, _ in cards_and_bodies]
    bodies = {c[0]: b for c, b in cards_and_bodies}
    skills.read = lambda e: bodies[e["id"]]
    return items


# A realistic web role: "python"/"web" recur across cards (so they are generic); each
# card's real topic is a distinctive term.
WEB_ROLE = [
    (("obf", "obfuscator 还原", "前端混淆字符串还原", ["web"]),
     "用 python 写 RC4 解码脚本，站点是前端 web 游戏，atob decodeURIComponent"),
    (("php", "PHP 反序列化", "pop 链构造", ["web"]),
     "php unserialize 字符串逃逸，python 辅助，web 服务"),
    (("ssrf", "gopher SSRF", "协议走私打内网", ["web"]),
     "gopher 协议打 redis，python requests，web 入口"),
    (("sqli", "SQL 注入", "联合与盲注", ["web"]),
     "union select，python sqlmap，web 参数"),
]


def test_offtopic_card_not_pulled_up_by_generic_words():
    items = setup(WEB_ROLE)
    q = ("Python Web 栈 Flask Jinja2 SSTI 模板注入 黑名单绕过 dict join attr "
         "沙箱逃逸 命令执行 文件读取")
    # No card covers SSTI; the only overlaps are generic python/web → nothing qualifies.
    assert skills.search(items, q) == "", "generic words must not surface an off-topic card"


def test_distinctive_term_in_body_surfaces_coverage():
    # Mirrors web-python: the card's topic word lives only in its body, not its metadata.
    items = setup(WEB_ROLE + [
        (("py", "Python 语言专题", "Python Web 栈利用", ["web"]),
         "命令执行 沙箱逃逸 反序列化 模板注入 文件读取，flask jinja2 lipsum globals"),
    ])
    out = skills.search(items, "SSTI 模板注入 黑名单绕过")
    assert "Python 语言专题" in out, "a rare term in the body must still surface coverage"


def test_generic_query_matches_nothing():
    items = setup(WEB_ROLE)
    assert skills.search(items, "python web") == ""


def test_ontopic_name_hit_ranks_first():
    items = setup(WEB_ROLE)
    out = skills.search(items, "gopher SSRF 内网")
    assert out.startswith("## gopher SSRF"), "name/tag hit on a distinctive term ranks first"


if __name__ == "__main__":
    _orig = skills.read
    try:
        test_offtopic_card_not_pulled_up_by_generic_words()
        test_distinctive_term_in_body_surfaces_coverage()
        test_generic_query_matches_nothing()
        test_ontopic_name_hit_ranks_first()
    finally:
        skills.read = _orig
    print("PASS skill search test")
