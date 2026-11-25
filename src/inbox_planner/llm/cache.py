"""Record-and-replay cache in front of any LLM client.

Each answer is stored under the fingerprint of its request (model, prompts,
schema). Change a prompt and the old answer no longer matches: replay mode then
fails loudly instead of serving a stale answer. The stored file holds the
answer and a short tag, never the prompt, so no mail text ends up on disk.
"""

import json
from datetime import UTC, datetime
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

from inbox_planner.llm.base import CacheMiss, LLMClient, LLMRequest, LLMResponse, Usage

DEMO_CACHE: Traversable = files("inbox_planner") / "demo_data" / "llm_cache"


class CachedClient:
    """Replays recorded answers; records missing ones only if a live client is given."""

    def __init__(self, cache_dir: Path | Traversable = DEMO_CACHE, live: LLMClient | None = None):
        self.cache_dir = cache_dir
        self.live = live
        self.name = f"cache+{live.name}" if live else "replay"

    def complete(self, request: LLMRequest) -> LLMResponse:
        key = request.cache_key()
        entry = self.cache_dir / request.model / f"{key}.json"
        if entry.is_file():
            stored = json.loads(entry.read_text(encoding="utf-8"))
            return LLMResponse(
                data=stored["data"],
                model=stored["model"],
                usage=Usage(**stored["usage"]),
                duration_ms=stored["duration_ms"],
                from_cache=True,
            )
        if self.live is None:
            raise CacheMiss(f"no recorded answer for {request.tag or key[:12]} on {request.model}")

        response = self.live.complete(request)
        target = Path(str(entry))
        target.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "tag": request.tag,
            "requested_model": request.model,
            "model": response.model,
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "recorded_with": self.live.name,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "duration_ms": response.duration_ms,
            "data": response.data,
        }
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return response
