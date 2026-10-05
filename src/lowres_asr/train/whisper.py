"""Fine-tune Whisper on a Common Voice split.

Whisper has no language token for Gojri or Pahari. Both are written in Urdu
orthography and are phonologically close to Urdu/Punjabi, so we condition the
decoder on `cfg.whisper_language` (Urdu by default) and let fine-tuning adapt the
model. This is the standard trick for languages outside Whisper's 99 and works
well in practice for Perso-Arabic-script languages.

Everything heavy is imported inside `train()` so the rest of the package stays
usable without torch installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import LanguageConfig
from ..data.common_voice import load_common_voice
from ..text.normalize import normalize_for_asr


@dataclass
class DataCollatorSpeechSeq2Seq:
    processor: Any

    def __call__(self, features: list[dict[str, Any]]) -> dict[str, Any]:
        input_features = [{"input_features": f["input_features"]} for f in features]
        batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")

        label_features = [{"input_ids": f["labels"]} for f in features]
        labels_batch = self.processor.tokenizer.pad(label_features, return_tensors="pt")
        labels = labels_batch["input_ids"].masked_fill(labels_batch.attention_mask.ne(1), -100)
        # Trainer prepends the decoder start token itself; strip it if the tokenizer added it.
        if (labels[:, 0] == self.processor.tokenizer.bos_token_id).all().cpu().item():
            labels = labels[:, 1:]
        batch["labels"] = labels
        return batch


def train(cfg: LanguageConfig, cv_dir: Path, output_dir: Path, max_train_samples: int | None = None) -> None:
    import evaluate
    import torch
    from transformers import (
        Seq2SeqTrainer,
        Seq2SeqTrainingArguments,
        WhisperForConditionalGeneration,
        WhisperProcessor,
    )

    tc = cfg.train
    processor = WhisperProcessor.from_pretrained(
        tc.base_model, language=cfg.whisper_language, task="transcribe"
    )
    model = WhisperForConditionalGeneration.from_pretrained(tc.base_model)
    model.generation_config.language = cfg.whisper_language
    model.generation_config.task = "transcribe"
    model.generation_config.forced_decoder_ids = None

    ds = load_common_voice(cv_dir, cfg)
    if "dev" not in ds:
        raise RuntimeError("Need a dev split for evaluation during training")
    if max_train_samples:
        ds["train"] = ds["train"].select(range(min(max_train_samples, len(ds["train"]))))

    max_len = int(tc.max_audio_seconds * tc.sampling_rate)

    def prepare(batch: dict[str, Any]) -> dict[str, Any]:
        audio = batch["audio"]
        batch["input_length"] = len(audio["array"])
        batch["input_features"] = processor.feature_extractor(
            audio["array"], sampling_rate=audio["sampling_rate"]
        ).input_features[0]
        batch["labels"] = processor.tokenizer(batch["text"]).input_ids
        return batch

    ds = ds.map(prepare, remove_columns=ds["train"].column_names, num_proc=1)
    ds = ds.filter(lambda n: 0 < n <= max_len, input_columns=["input_length"])

    wer_metric = evaluate.load("wer")
    cer_metric = evaluate.load("cer")

    def compute_metrics(pred: Any) -> dict[str, float]:
        pred_ids = pred.predictions
        label_ids = pred.label_ids
        label_ids[label_ids == -100] = processor.tokenizer.pad_token_id
        hyps = processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
        refs = processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)
        hyps = [normalize_for_asr(h, cfg.text) for h in hyps]
        refs = [normalize_for_asr(r, cfg.text) for r in refs]
        # jiwer rejects empty references; substitute a placeholder so one bad row
        # does not abort evaluation.
        refs = [r if r else "<empty>" for r in refs]
        return {
            "wer": 100 * wer_metric.compute(predictions=hyps, references=refs),
            "cer": 100 * cer_metric.compute(predictions=hyps, references=refs),
        }

    use_mps = torch.backends.mps.is_available()
    args = Seq2SeqTrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=tc.batch_size,
        per_device_eval_batch_size=tc.batch_size,
        gradient_accumulation_steps=tc.grad_accum,
        learning_rate=tc.learning_rate,
        warmup_steps=tc.warmup_steps,
        max_steps=tc.max_steps,
        gradient_checkpointing=True,
        fp16=torch.cuda.is_available(),
        bf16=False,
        eval_strategy="steps",
        eval_steps=tc.eval_steps,
        save_steps=tc.save_steps,
        save_total_limit=2,
        predict_with_generate=True,
        generation_max_length=225,
        logging_steps=25,
        report_to=["none"],
        load_best_model_at_end=True,
        metric_for_best_model="wer",
        greater_is_better=False,
        dataloader_num_workers=0 if use_mps else 2,
        remove_unused_columns=False,
    )

    trainer = Seq2SeqTrainer(
        args=args,
        model=model,
        train_dataset=ds["train"],
        eval_dataset=ds["dev"],
        data_collator=DataCollatorSpeechSeq2Seq(processor),
        compute_metrics=compute_metrics,
        processing_class=processor.feature_extractor,
    )
    trainer.train()
    trainer.save_model(str(output_dir / "final"))
    processor.save_pretrained(str(output_dir / "final"))
