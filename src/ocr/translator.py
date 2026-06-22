"""
CyberLens — IndicTrans2 Hindi Translator
==========================================
Translates Hindi/regional language OCR text to English
for downstream LLM analysis.

Model: ai4bharat/indictrans2-indic-en-dist-200M (HuggingFace, local)
Supported: Hindi (hi), Punjabi (pa), Bengali (bn), Marathi (mr), Tamil (ta)

Author: CyberLens Team — GPCSSI Internship
"""

import logging
import os
import re
from typing import Optional

logger = logging.getLogger("cyberlens.ocr.translator")

# Language code → IndicTrans2 source tag
LANG_CODES = {
    "hi": "hin_Deva",
    "pa": "pan_Guru",
    "bn": "ben_Beng",
    "mr": "mar_Deva",
    "ta": "tam_Taml",
    "te": "tel_Telu",
    "gu": "guj_Gujr",
}
TARGET_LANG = "eng_Latn"


class IndicTranslator:
    """Translates Indian regional languages to English.

    Uses ai4bharat/indictrans2 locally when available.
    Falls back to a transliteration heuristic for pure Latin script
    (Hinglish/Roman Urdu already readable by English LLMs).
    """

    _model = None
    _tokenizer = None
    _loaded = False

    def __init__(self):
        self._try_load()

    def _try_load(self) -> None:
        if IndicTranslator._loaded:
            return
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            model_name = "ai4bharat/indictrans2-indic-en-dist-200M"
            logger.info("Loading IndicTrans2 model (this may take a moment)...")
            IndicTranslator._tokenizer = AutoTokenizer.from_pretrained(
                model_name, trust_remote_code=True
            )
            IndicTranslator._model = AutoModelForSeq2SeqLM.from_pretrained(
                model_name, trust_remote_code=True
            )
            IndicTranslator._loaded = True
            logger.info("IndicTrans2 loaded")
        except ImportError:
            logger.info("transformers not installed — translator disabled")
            IndicTranslator._loaded = True
        except Exception as e:
            logger.warning("IndicTrans2 load failed: %s — translator disabled", e)
            IndicTranslator._loaded = True

    def translate(
        self,
        text: str,
        source_lang: str = "hi",
        target_lang: str = "en",
    ) -> str:
        """Translate text from source language to English.

        Args:
            text: Input text.
            source_lang: ISO language code (hi, pa, bn, mr, ta).
            target_lang: Target language code (en).

        Returns:
            Translated English text.
        """
        if not text or not text.strip():
            return text

        # If text is already mostly Latin script, return as-is (Hinglish)
        if self._is_mostly_latin(text):
            return text

        if not (self._model and self._tokenizer):
            return self._fallback_translate(text)

        src_code = LANG_CODES.get(source_lang, "hin_Deva")

        try:
            import torch
            inputs = self._tokenizer(
                text,
                src_lang=src_code,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )

            with torch.no_grad():
                generated = self._model.generate(
                    **inputs,
                    forced_bos_token_id=self._tokenizer.lang_code_to_id[TARGET_LANG],
                    max_new_tokens=256,
                )

            translated = self._tokenizer.batch_decode(
                generated, skip_special_tokens=True
            )
            return translated[0] if translated else text

        except Exception as e:
            logger.debug("Translation failed: %s", e)
            return self._fallback_translate(text)

    def translate_if_hindi(self, text: str) -> str:
        """Translate only if text contains significant Hindi script."""
        if not text:
            return text
        devanagari = sum(1 for c in text if "\u0900" <= c <= "\u097F")
        if devanagari > 5:
            return self.translate(text, source_lang="hi")
        return text

    @staticmethod
    def _is_mostly_latin(text: str) -> bool:
        latin = sum(1 for c in text if c.isascii())
        return latin > len(text) * 0.7

    @staticmethod
    def _fallback_translate(text: str) -> str:
        """Minimal fallback: return original text (LLMs handle Hindi reasonably)."""
        return text

    @property
    def available(self) -> bool:
        return self._model is not None
