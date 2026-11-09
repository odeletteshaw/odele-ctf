"""XXE (XML external entity). A contact endpoint parses XML and expands entities,
including SYSTEM entities that read "files". The filesystem is a VIRTUAL dict, so an
external entity resolves only to the challenge's fake files, never the real host.
"""

import re

from ._harness import Request, start_server

DESCRIPTION = "A contact form that accepts an XML message (Content-Type: application/xml)."

HOME = """<h1>Contact us</h1>
<p>POST your message as XML to /contact, for example:</p>
<pre>&lt;contact&gt;&lt;name&gt;Bob&lt;/name&gt;&lt;msg&gt;Hello&lt;/msg&gt;&lt;/contact&gt;</pre>"""


def _parse_xml(xml: str, vfs: dict[str, str]) -> tuple[str, str]:
    """Collect entity declarations, resolving SYSTEM ones against the virtual FS,
    then expand &name; references in the <name> and <msg> fields."""
    entities: dict[str, str] = {}
    for name, uri in re.findall(r'<!ENTITY\s+(\w+)\s+SYSTEM\s+"([^"]+)"\s*>', xml):
        entities[name] = vfs.get(uri, f"[could not resolve {uri}]")
    for name, value in re.findall(r'<!ENTITY\s+(\w+)\s+"([^"]*)"\s*>', xml):
        entities[name] = value

    def expand(text: str) -> str:
        return re.sub(r"&(\w+);", lambda m: entities.get(m.group(1), m.group(0)), text)

    name_match = re.search(r"<name>(.*?)</name>", xml, re.S)
    msg_match = re.search(r"<msg>(.*?)</msg>", xml, re.S)
    name = expand(name_match.group(1)) if name_match else ""
    msg = expand(msg_match.group(1)) if msg_match else ""
    return name, msg


def start(flag: str) -> tuple[object, str]:
    vfs = {"file:///flag.txt": flag, "file:///etc/hostname": "web-01"}

    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, HOME, None
        if req.route == "/contact" and req.method == "POST":
            # The vulnerability: XML is parsed with external entities enabled.
            name, msg = _parse_xml(req.body.decode(errors="replace"), vfs)
            return 200, f"Thanks, {name}. We received: {msg}", {"Content-Type": "text/plain"}
        return 404, "Not found", None

    return start_server(route)
