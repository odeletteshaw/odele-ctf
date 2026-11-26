"""Command injection. A "diagnostics" endpoint builds a shell command from user
input. The shell is SIMULATED against a virtual filesystem, so no real command runs
on the host; the injection still works exactly as it would against a naive os.system.
"""

import re
import shlex

from ._harness import Request, start_server

DESCRIPTION = "A network diagnostics tool that pings a host you provide."

FORM = """<h1>Network diagnostics</h1>
<form method="post" action="/ping">
  <input name="host" placeholder="host to ping">
  <button>Ping</button>
</form>"""


def _virtual_shell(command: str, flag: str) -> str:
    """Run a few commands against a fake filesystem. Supports ; and | chaining,
    which is what makes the injection land. Nothing reaches the real OS."""
    files = {"flag.txt": flag, "app.py": "# diagnostics service\n# runs: ping -c1 <host>\n"}
    env = {"FLAG": flag, "USER": "web"}
    outputs = []
    for part in re.split(r"[;\n]|&&|\|\||\|", command):
        part = part.strip()
        if not part:
            continue
        try:
            tokens = shlex.split(part)
        except ValueError:
            outputs.append(f"sh: syntax error near: {part}")
            continue
        if not tokens:
            continue
        name, args = tokens[0], tokens[1:]
        if name == "ping":
            host = args[-1] if args else ""
            outputs.append(f"PING {host}: 1 packets transmitted, 1 received, 0% packet loss")
        elif name == "echo":
            outputs.append(" ".join(args))
        elif name == "cat":
            for f in args:
                outputs.append(files.get(f, f"cat: {f}: No such file or directory"))
        elif name == "ls":
            outputs.append("  ".join(sorted(files)))
        elif name == "pwd":
            outputs.append("/app")
        elif name in ("id", "whoami"):
            outputs.append("web" if name == "whoami" else "uid=1000(web) gid=1000(web)")
        elif name == "env":
            outputs.extend(f"{k}={v}" for k, v in env.items())
        else:
            outputs.append(f"sh: {name}: command not found")
    return "\n".join(outputs)


def start(flag: str) -> tuple[object, str]:
    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, FORM, None
        if req.route == "/ping" and req.method == "POST":
            host = req.form.get("host", "")
            # The vulnerability: user input is concatenated into a shell command.
            command = f"ping -c1 {host}"
            return 200, f"<pre>$ {command}\n{_virtual_shell(command, flag)}</pre>", None
        return 404, "Not found", None

    return start_server(route)
