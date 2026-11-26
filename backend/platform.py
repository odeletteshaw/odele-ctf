"""CTF2 platform REST client for the Agent play API.

A thin wrapper over the endpoints an Agent is allowed to use: identify itself, find
unsolved challenges, read a challenge and download its attachments, start/read a target
environment, submit a flag, and log solution notes. Auth is `Authorization: Bearer
<CTF2_AGENT_TOKEN>`; tokens are stored in the console DB (editable from the Settings
page) with the environment as a fallback.

Responses use the envelope {success, data|error}. Errors raise PlatformError with the
code/key from `error`.
"""

import os

import httpx

from backend.settings import settings  # also loads .env via agent.config

DEFAULT_BASE = "https://ctf2.dasctf.com"


def list_tokens() -> list[str]:
    """CTF2 agent tokens: the DB-configured list, or the .env/environment fallback."""
    return settings.tokens()


class PlatformError(Exception):
    def __init__(self, code, message, retryable=False, retry_after_ms=None, hint=None,
                 status=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.retry_after_ms = retry_after_ms
        self.hint = hint
        self.status = status


class PlatformClient:
    def __init__(self, token: str | None = None, base: str | None = None):
        tokens = list_tokens()
        self.token = token or os.environ.get("CTF2_AGENT_TOKEN") or (tokens[0] if tokens else None)
        if not self.token:
            raise RuntimeError("no CTF2 agent token set (add CTF2_AGENT_TOKEN_0 to .env)")
        self.client = httpx.Client(
            base_url=base or DEFAULT_BASE,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=30,
        )

    def close(self) -> None:
        self.client.close()

    def _request(self, method: str, path: str, **kwargs) -> dict:
        response = self.client.request(method, path, **kwargs)
        try:
            body = response.json()
        except Exception:
            body = None
        if isinstance(body, dict) and (body.get("success") is False or response.status_code >= 400):
            err = body.get("error") or {}
            if isinstance(err, dict):
                code = err.get("code", f"HTTP_{response.status_code}")
                message = err.get("message") or err.get("key") or code or response.text[:200]
                raise PlatformError(
                    code=code, message=message,
                    retryable=bool(err.get("retryable", False)),
                    retry_after_ms=err.get("retry_after_ms"),
                    hint=err.get("hint"),
                    status=response.status_code,
                )
            raise PlatformError(f"HTTP_{response.status_code}", response.text[:200],
                                status=response.status_code)
        if isinstance(body, dict) and "data" in body:
            return body.get("data", body)
        return body

    # --- agent identity / discovery ----------------------------------------
    def whoami(self) -> dict:
        return self._request("GET", "/api/open/v1/user/agent/me/")

    def next_challenges(self, limit: int = 1, category: str | None = None,
                        source: str = "practice", difficulty: str | None = None) -> dict:
        params: dict = {"limit": limit, "source": source}
        if category:
            params["category"] = category
        if difficulty:
            params["difficulty"] = difficulty
        return self._request(
            "GET", "/api/open/v1/user/agent/next-challenges/", params=params,
        )

    # --- practice ----------------------------------------------------------
    def list_challenges(self, ground_id, **params) -> dict:
        return self._request(
            "GET", f"/api/open/v1/user/practice/{ground_id}/challenges/", params=params,
        )

    def get_challenge(self, ground_id, challenge_id) -> dict:
        return self._request(
            "GET", f"/api/open/v1/user/practice/{ground_id}/challenges/{challenge_id}/",
        )

    def get_attachment_url(self, ground_id, challenge_id, file_id) -> str:
        """Return a signed download URL valid for ~5 minutes."""
        data = self._request(
            "GET",
            f"/api/open/v1/user/practice/{ground_id}/challenges/{challenge_id}"
            f"/files/{file_id}/download/",
        )
        if isinstance(data, dict) and "url" in data:
            return data["url"]
        if isinstance(data, str):
            return data
        raise PlatformError("invalid_response", f"unexpected attachment response: {data!r}")

    def download_attachment(self, ground_id, challenge_id, file_id, dest_dir) -> str:
        """Download an attachment into dest_dir; returns the saved file path."""
        url = self.get_attachment_url(ground_id, challenge_id, file_id)
        resp = httpx.get(url, follow_redirects=True, timeout=180)
        resp.raise_for_status()
        name = file_id
        cd = resp.headers.get("content-disposition", "")
        if "filename=" in cd:
            name = cd.split("filename=", 1)[1].strip('";')
        path = os.path.join(dest_dir, name)
        with open(path, "wb") as f:
            f.write(resp.content)
        return path

    # --- environment (container challenges) ---------------------------------
    def get_environment(self, ground_id, challenge_id) -> dict:
        return self._request(
            "GET", f"/api/open/v1/user/practice/{ground_id}/challenges/{challenge_id}/environment/",
        )

    def start_environment(self, ground_id, challenge_id) -> dict:
        return self._request(
            "POST",
            f"/api/open/v1/user/practice/{ground_id}/challenges/{challenge_id}/environment/start/",
            json={},
        )

    def delete_environment(self, ground_id, challenge_id) -> dict:
        return self._request(
            "DELETE",
            f"/api/open/v1/user/practice/{ground_id}/challenges/{challenge_id}/environment/",
        )

    def extend_environment(self, ground_id, challenge_id) -> dict:
        return self._request(
            "POST",
            f"/api/open/v1/user/practice/{ground_id}/challenges/{challenge_id}/environment/extend/",
            json={},
        )

    # --- submit / notes ----------------------------------------------------
    def submit_flag(self, ground_id, challenge_id, flag: str, sub_flag_id=None) -> dict:
        body = {"confirmation": True, "flag": flag}
        if sub_flag_id is not None:
            body["sub_flag_id"] = sub_flag_id
        return self._request(
            "POST",
            f"/api/open/v1/user/practice/{ground_id}/challenges/{challenge_id}/submit/",
            json=body,
        )

    def log_note(self, challenge_id: str, kind: str, content: str) -> dict:
        return self._request(
            "POST", "/api/open/v1/user/agent/notes/",
            json={"challenge_id": challenge_id, "kind": kind, "content": content},
        )
