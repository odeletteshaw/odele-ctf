"""Server-side template injection. User input is embedded into a template and
rendered, so {{ expr }} in the input gets evaluated. The evaluator is a RESTRICTED
AST walker (arithmetic and dict lookups only — no calls, no imports, no real object
access), so {{7*7}} confirms the bug and {{config.SECRET}} reaches the flag, with no
risk of real code execution.
"""

import ast
import re

from ._harness import Request, start_server

DESCRIPTION = "A greeting-card generator. It personalizes a message with your name."

FORM = """<h1>Greeting cards</h1>
<form method="post" action="/card">
  <input name="name" placeholder="your name">
  <button>Make card</button>
</form>"""

_ALLOWED_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a // b if b else 0,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a**b,
}


def _eval(node: ast.AST, context: dict):
    if isinstance(node, ast.Expression):
        return _eval(node.body, context)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_eval(node.left, context), _eval(node.right, context))
    if isinstance(node, ast.Name):
        return context[node.id]
    if isinstance(node, ast.Attribute):
        return _eval(node.value, context)[node.attr]
    if isinstance(node, ast.Subscript):
        return _eval(node.value, context)[_eval(node.slice, context)]
    raise ValueError("unsupported expression")


def _render(template: str, context: dict) -> str:
    def replace(match: re.Match) -> str:
        expr = match.group(1).strip()
        try:
            return str(_eval(ast.parse(expr, mode="eval"), context))
        except Exception as error:
            return f"<error: {error}>"

    return re.sub(r"\{\{(.*?)\}\}", replace, template)


def start(flag: str) -> tuple[object, str]:
    context = {"config": {"SECRET": flag}, "app_name": "cards"}

    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, FORM, None
        if req.route == "/card" and req.method == "POST":
            name = req.form.get("name", "")
            # The vulnerability: user input becomes part of the template that is rendered.
            return 200, _render(f"<h2>Hello, {name}!</h2>", context), None
        return 404, "Not found", None

    return start_server(route)
