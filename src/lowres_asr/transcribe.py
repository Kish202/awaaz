"""Run a (fine-tuned or stock) Whisper checkpoint over audio files or a CV split."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from .config import LanguageConfig


class WhisperTranscriber:
    def __init__(self, model_path: str, cfg: LanguageConfig, device: str | None = None):
        import torch
        from transformers import WhisperForConditionalGeneration, WhisperProcessor

        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        self.device = device
        self.cfg = cfg
        self.processor = WhisperProcessor.from_pretrained(
            model_path, language=cfg.whisper_language, task="transcribe"
        )
        self.model = WhisperForConditionalGeneration.from_pretrained(model_path).to(device)
        self.model.eval()

    def _load(self, path: Path) -> Any:
        import librosa

        audio, _ = librosa.load(str(path), sr=self.cfg.train.sampling_rate, mono=True)
        return audio

    def transcribe_arrays(self, arrays: list[Any], batch_size: int = 8) -> list[str]:
        import torch

        out: list[str] = []
        for i in range(0, len(arrays), batch_size):
            chunk = arrays[i : i + batch_size]
            feats = self.processor.feature_extractor(
                chunk, sampling_rate=self.cfg.train.sampling_rate, return_tensors="pt"
            ).input_features.to(self.device)
            with torch.no_grad():
                ids = self.model.generate(
                    feats,
                    language=self.cfg.whisper_language,
                    task="transcribe",
                    max_new_tokens=225,
                )
            out.extend(self.processor.batch_decode(ids, skip_special_tokens=True))
        return [s.strip() for s in out]

    def transcribe_files(self, paths: Iterable[Path], batch_size: int = 8) -> Iterator[tuple[Path, str]]:
        paths = list(paths)
        for i in range(0, len(paths), batch_size):
            chunk = paths[i : i + batch_size]
            arrays = [self._load(p) for p in chunk]
            yield from zip(chunk, self.transcribe_arrays(arrays, batch_size=batch_size))
