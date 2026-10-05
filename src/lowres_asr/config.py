"""Typed access to the per-language YAML configs in `configs/`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"


@dataclass
class TextConfig:
    preserve_chars: list[str] = field(default_factory=list)
    strip_diacritics: bool = True
    strip_zwnj: bool = False
    digits: str = "ascii"  # ascii | urdu | keep


@dataclass
class SentenceConfig:
    min_words: int = 2
    max_words: int = 14
    reject_digits: bool = True
    reject_latin: bool = True
    reject_urls: bool = True
    terminators: list[str] = field(default_factory=lambda: ["۔", "؟", "!", ".", "?"])


@dataclass
class TrainConfig:
    base_model: str = "openai/whisper-small"
    sampling_rate: int = 16000
    max_audio_seconds: float = 30.0
    batch_size: int = 8
    grad_accum: int = 2
    learning_rate: float = 1e-5
    warmup_steps: int = 100
    max_steps: int = 2000
    eval_steps: int = 250
    save_steps: int = 250


@dataclass
class LanguageConfig:
    code: str
    name: str
    common_voice_locale: str
    whisper_language: str
    text: TextConfig = field(default_factory=TextConfig)
    sentences: SentenceConfig = field(default_factory=SentenceConfig)
    train: TrainConfig = field(default_factory=TrainConfig)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LanguageConfig:
        return cls(
            code=d["code"],
            name=d["name"],
            common_voice_locale=d.get("common_voice_locale", d["code"]),
            whisper_language=d.get("whisper_language", "urdu"),
            text=TextConfig(**d.get("text", {})),
            sentences=SentenceConfig(**d.get("sentences", {})),
            train=TrainConfig(**d.get("train", {})),
        )


def load_config(name_or_path: str) -> LanguageConfig:
    """Load a config by language code (`gju`, `phr`) or by explicit YAML path."""
    path = Path(name_or_path)
    if not path.exists():
        path = CONFIG_DIR / f"{name_or_path}.yaml"
    if not path.exists():
        available = ", ".join(p.stem for p in sorted(CONFIG_DIR.glob("*.yaml")))
        raise FileNotFoundError(f"No config '{name_or_path}'. Available: {available}")
    with path.open(encoding="utf-8") as f:
        return LanguageConfig.from_dict(yaml.safe_load(f))
