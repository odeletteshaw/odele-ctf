"""Turn a CTF2 platform challenge into our solve spec (a custom target).

prepare_challenge() fetches the challenge detail, downloads attachments into a temp dir,
starts (and waits for) the container environment if the challenge has one, and returns a
spec that backend.builder.build_task() can run, plus the metadata needed to submit the flag.
Only the categories our custom solver supports (web / crypto / forensics) are returned;
anything else yields None so the caller can skip it.
"""

import tempfile
import time

from backend.platform import PlatformClient, PlatformError

# platform category string -> our custom direction (build_task supports these).
SUPPORTED = {"WEB": "web", "CRYPTO": "crypto", "MISC": "misc", "FORENSICS": "forensics"}

# our custom direction -> platform category string (reverse of SUPPORTED), for filtering
# next-challenges by category so each direction only fetches its own challenges.
PLATFORM_CATEGORY = {v: k for k, v in SUPPORTED.items()}

_ENV_POLLS = 24  # 24 * 5s = up to 2 minutes for a container to become ready

# The platform rejects start_environment with RATE_LIMIT_EXCEEDED when containers are
# started too fast back-to-back. Space starts out and back off longer on a retryable
# rejection instead of hammering the endpoint and erroring a whole batch.
_ENV_START_GAP = 20.0  # minimum seconds between start_environment calls
_RATE_LIMIT_BACKOFF = 20.0  # seconds to wait before retrying a retryable rejection
_last_env_start = 0.0


def _throttled_start(client: PlatformClient, ground_id, challenge_id) -> dict:
    """start_environment with a minimum gap between calls (rate-limit avoidance)."""
    global _last_env_start
    wait = _ENV_START_GAP - (time.time() - _last_env_start)
    if wait > 0:
        time.sleep(wait)
    _last_env_start = time.time()
    return client.start_environment(ground_id, challenge_id)


def _tcp_mode_url(u: str) -> str | None:
    """DAS CTF2 also exposes a TCP-mode endpoint that bypasses the OpenResty proxy
    (which overwrites X-Forwarded-For). Derive it from an HTTP access URL:
    http://<id>.http-ctf2.dasctf.com:80 -> https://<id>.tcp-ctf2.dasctf.com:9999"""
    if ".http-ctf2.dasctf.com" not in u:
        return None
    host = u.split("//")[1].split("/")[0].split(":")[0]
    return f"https://{host.replace('http-ctf2', 'tcp-ctf2')}:9999"


def _access_urls(env: dict) -> list[str]:
    urls: list[str] = []
    u = env.get("access_url")
    if u:
        urls.append(u)
        tcp = _tcp_mode_url(u)
        if tcp and tcp not in urls:
            urls.append(tcp)
    for au in env.get("access_urls") or []:
        uu = au.get("url")
        if uu and uu not in urls:
            urls.append(uu)
            tcp = _tcp_mode_url(uu)
            if tcp and tcp not in urls:
                urls.append(tcp)
    return urls


def _wait_environment(client: PlatformClient, ground_id, challenge_id) -> list[str]:
    """Start (or reuse) a challenge environment and wait for its access URL(s), retrying
    once if the first start never becomes ready."""
    last_err: PlatformError | None = None
    for attempt in range(2):
        restarts = 0
        none_streak = 0
        ready = None
        try:
            _throttled_start(client, ground_id, challenge_id)
        except PlatformError as e:
            last_err = e  # may already be running; fall through to polling
            # A transient rate-limit / quota rejection is retryable: honor its backoff and
            # retry the start once instead of sitting in a doomed "none" poll.
            if e.retryable:
                time.sleep((e.retry_after_ms or _RATE_LIMIT_BACKOFF * 1000) / 1000)
                try:
                    _throttled_start(client, ground_id, challenge_id)
                except PlatformError as e2:
                    last_err = e2
        for _ in range(_ENV_POLLS):
            try:
                env = client.get_environment(ground_id, challenge_id)
            except PlatformError as e:
                last_err = e
                env = {}
            if env.get("access_ready"):
                ready = _access_urls(env)
                break
            status = env.get("status")
            if status == "error" and restarts < 1:
                restarts += 1
                try:
                    _throttled_start(client, ground_id, challenge_id)
                except PlatformError as e:
                    last_err = e
                none_streak = 0
                continue
            if status == "none":
                # "none" is also the brief state right after start (before "starting"); only
                # give up after it persists for a few polls — start genuinely failed then.
                none_streak += 1
                if none_streak >= 3:
                    break
            else:
                none_streak = 0
            time.sleep(5)
        if ready:
            return ready
        # never became ready — clean up and retry once before giving up
        try:
            client.delete_environment(ground_id, challenge_id)
        except PlatformError:
            pass
        time.sleep(2)
    detail = ""
    if last_err is not None:
        detail = f" (last start error: {last_err.code} {last_err.message})"
    raise RuntimeError(f"container environment did not become ready{detail}")


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
        if not urls:
            # Don't start a session with no target — it would just "run" and fail.
            raise RuntimeError("container environment did not become ready")

    spec = {
        "kind": "custom",
        "category": direction,
        "urls": urls,
        "description": challenge.get("description", ""),
        "attachments": attachments,
        # CTF2 platform flags are CTF2{...}; a strict prefix prevents decoy/CSS
        # lookalikes from being reported as the flag.
        "flag_prefix": "CTF2",
    }
    meta = {
        "challenge_id": challenge_id,
        "ground_id": ground_id,
        "name": challenge.get("name") or item.get("name", "challenge"),
        "category": direction,
    }
    return spec, meta
