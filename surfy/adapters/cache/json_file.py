import json
import logging
from pathlib import Path

from surfy.domain.models.cache import CachedScenario
from surfy.domain.ports.cache import CachePort

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path.home() / ".surfy" / "scenario_cache.json"


class JsonFileCacheAdapter(CachePort):
    """CachedScenario를 JSON 파일로 영속화하는 어댑터."""

    def __init__(self, path: Path = _DEFAULT_PATH):
        self._path = path

    def get(self, cache_key: str) -> CachedScenario | None:
        if not self._path.exists():
            return None
        try:
            data: dict = json.loads(self._path.read_text(encoding="utf-8"))
            entry = data.get(cache_key)
            if entry is None:
                return None
            return CachedScenario.model_validate(entry)
        except Exception as e:
            logger.warning("Cache read failed: %s", e)
            return None

    def set(self, scenario: CachedScenario) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data: dict = {}
            if self._path.exists():
                try:
                    data = json.loads(self._path.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
            data[scenario.cache_key] = scenario.model_dump()
            self._path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            logger.info(
                "Cache stored: key=%s command=%s", scenario.cache_key, scenario.command_normalized
            )
        except Exception as e:
            logger.warning("Cache write failed: %s", e)
