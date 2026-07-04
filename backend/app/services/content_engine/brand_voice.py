import yaml
import os
from functools import lru_cache
from pathlib import Path

from app.config import settings


class BrandVoice:
    def __init__(self, data: dict):
        self.name: str = data["name"]
        self.tone: str = data["tone"]
        self.personality: str = data["personality"]
        self.audience: str = data["audience"]
        self.content_pillars: list[str] = data.get("content_pillars", [])
        self.hashtags: list[str] = data.get("hashtags", [])
        self.avoid: list[str] = data.get("avoid", [])
        self.platform_notes: dict = data.get("platform_notes", {})
        self.system_prompt: str = data.get("system_prompt", "")

    def get_platform_instructions(self, platform: str) -> str:
        return self.platform_notes.get(platform, "")


@lru_cache(maxsize=32)
def load_brand_voice(project_slug: str) -> BrandVoice:
    config_dir = Path(settings.brand_configs_dir)
    config_file = config_dir / f"{project_slug.replace('-', '_')}.yaml"

    if not config_file.exists():
        config_file = config_dir / "dirco.yaml"

    with open(config_file) as f:
        data = yaml.safe_load(f)

    return BrandVoice(data)
