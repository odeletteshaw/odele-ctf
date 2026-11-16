"""Turn a CTF2 platform challenge into our solve spec (a custom target).

prepare_challenge() fetches the challenge detail, downloads attachments into a temp dir,
starts (and waits for) the container environment if the challenge has one, and returns a
spec that gui.builder.build_task() can run, plus the metadata needed to submit the flag.
Only the categories our custom solver supports (web / crypto / forensics) are returned;
anything else yields None so the caller can skip it.
"""

import tempfile
import time

from .platform import PlatformClient, PlatformError

# platform category string -> our custom direction (build_task supports these).
SUPPORTED = {"WEB": "web", "CRYPTO": "crypto", "MISC": "misc", "FORENSICS": "forensics"}

_ENV_POLLS = 24  # 24 * 5s = up to 2 minutes for a container to become ready


def _access_urls(env: dict) -> list[str]:
    urls: list[str] = []
    u = env.get("access_url")
    if u:
        urls.append(u)
    for au in env.get("access_urls") or []:
        uu = au.get("url")
        if uu and uu not in urls:
            urls.append(uu)
    return urls


def _wait_environment(client: PlatformClient, ground_id, challenge_id) -> list[str]:
    """Start (or reuse) a challenge environment and wait for its access URL(s)."""
    restarts = 0
    try:
        client.start_environment(ground_id, challenge_id)
    except PlatformError:
        pass  # may already be running; fall through to polling
    for _ in range(_ENV_POLLS):
        try:
            env = client.get_environment(ground_id, challenge_id)
        except PlatformError:
            env = {}
        if env.get("access_ready"):
            return _access_urls(env)
        status = env.get("status")
        if status == "error" and restarts < 1:
            restarts += 1
            try:
                client.start_environment(ground_id, challenge_id)
            except PlatformError:
                pass
        elif status == "none":
            # start failed (e.g. environment quota already used by another challenge) — give up
            return []
        time.sleep(5)
    return []


def prepare_challenge(client: PlatformClient, item: dict) -> tuple[dict, dict] | None:
    """Return (spec, meta) for a challenge item, or None if its category is unsupported."""
    direction = SUPPORTED.get(str(item.get("category", "")).upper())
    if direction is None:
        return None

    ground_id = item["practice_ground_id"]
    challenge_id = item["id"]
    challenge = client.get_challenge(ground_id, challenge_id)

    urls: list[str] = []
    attachments: list[str] = []
    tmpdir = tempfile.mkdtemp(prefix="ctf2-")
    for f in challenge.get("files") or []:
        file_id = f.get("id")
        if file_id:
            attachments.append(client.download_attachment(ground_id, challenge_id, file_id, tmpdir))

    if challenge.get("has_container"):
        urls = _wait_environment(client, ground_id, challenge_id)

    spec = {
        "kind": "custom",
        "category": direction,
        "urls": urls,
        "description": challenge.get("description", ""),
        "attachments": attachments,
        "flag_prefix": "flag",
    }
    meta = {
        "challenge_id": challenge_id,
        "ground_id": ground_id,
        "name": challenge.get("name") or item.get("name", "challenge"),
        "category": direction,
    }
    return spec, meta
