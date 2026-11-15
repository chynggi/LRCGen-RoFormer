"""
MMS CTC forced alignment of known lyrics (no ASR step).

The user's own lyric words are aligned directly against the vocal audio with
MahmoudAshraf/mms-300m-1130-forced-aligner (wav2vec2 / MMS, 1100+ languages via
uroman romanization). A wildcard <star> token sits before every word and after
the last one, so vocals that are not in the lyrics (mash-up partners, ad-libs,
scat) are absorbed instead of dragging lyric words out of place.

Viterbi runs on torchaudio.functional.forced_align, so no compiled extension
is needed. Note: the default model weights are licensed CC-BY-NC 4.0.
"""

import math
import re
import unicodedata
from typing import Any, Dict, List, Optional

import numpy as np

from i18n import t as _t

MMS_MODEL_ID = "MahmoudAshraf/mms-300m-1130-forced-aligner"
SAMPLE_RATE = 16000

# uroman reads kanji with Chinese readings (世界 -> "shijie"), so Japanese goes
# through pykakasi (世界 -> "sekai") instead; particles are romanized as sung.
_JA_PARTICLES = {"は": "wa", "へ": "e", "を": "o"}

# ISO 639-1 (used across the app) -> ISO 639-3 (uroman language hints)
_ISO3 = {
    "ko": "kor", "en": "eng", "de": "deu", "fr": "fra", "es": "spa", "it": "ita",
    "pt": "por", "ru": "rus", "tr": "tur", "nl": "nld", "pl": "pol", "uk": "ukr",
}

_MODEL_CACHE: Dict[str, Any] = {}
_UROMAN = None
_KAKASI = None


def _load_model(device: str):
    if device not in _MODEL_CACHE:
        import torch
        from transformers import AutoModelForCTC, AutoTokenizer

        print(f"[MMS Align] {_t('mms.loading_model', model=MMS_MODEL_ID, device=device)}", flush=True)
        dtype = torch.float16 if device == "cuda" else torch.float32
        model = AutoModelForCTC.from_pretrained(MMS_MODEL_ID, dtype=dtype).to(device).eval()
        tokenizer = AutoTokenizer.from_pretrained(MMS_MODEL_ID, word_delimiter_token=None)
        vocab = {k.lower(): v for k, v in tokenizer.get_vocab().items()}
        blank = vocab.get("<blank>", tokenizer.pad_token_id)
        _MODEL_CACHE[device] = (model, vocab, blank)
    return _MODEL_CACHE[device]


def _load_audio_16k(audio_path: str) -> np.ndarray:
    try:
        import whisperx
        return whisperx.load_audio(audio_path)  # ffmpeg -> mono 16 kHz float32
    except Exception:
        import soundfile as sf
        import torch
        import torchaudio.functional as AF

        data, sr = sf.read(audio_path, dtype="float32", always_2d=True)
        wav = torch.from_numpy(data.mean(axis=1))
        if sr != SAMPLE_RATE:
            wav = AF.resample(wav, sr, SAMPLE_RATE)
        return wav.numpy()


def _emissions(model, wav, window_s: int = 30, context_s: int = 2, batch_size: int = 4):
    """Windowed CTC log-probs for long audio, plus a zero column for the <star> token."""
    import torch

    ratio = model.config.inputs_to_logits_ratio  # 320 samples = 20 ms per frame
    window = window_s * SAMPLE_RATE
    context = context_s * SAMPLE_RATE
    context_frames, window_frames = context // ratio, window // ratio

    if wav.size(0) < window:
        extension, context = 0, 0
        batches = wav.unsqueeze(0)
    else:
        extension = math.ceil(wav.size(0) / window) * window - wav.size(0)
        padded = torch.nn.functional.pad(wav, (context, context + extension))
        batches = padded.unfold(0, window + 2 * context, window)

    out = []
    with torch.inference_mode():
        for i in range(0, batches.size(0), batch_size):
            out.append(model(batches[i:i + batch_size]).logits)
    em = torch.cat(out, dim=0)
    if context > 0:
        em = em[:, context_frames:context_frames + window_frames]
    em = em.flatten(0, 1)
    if extension > 0:
        em = em[: -(extension // ratio)]
    em = torch.log_softmax(em.float(), dim=-1)
    em = torch.cat([em, torch.zeros(em.size(0), 1, device=em.device)], dim=1)
    return em.cpu(), ratio / SAMPLE_RATE


def _romanize_ja(text: str) -> str:
    global _KAKASI
    if _KAKASI is None:
        import pykakasi
        _KAKASI = pykakasi.kakasi()
    return "".join(_JA_PARTICLES.get(t["orig"], t["hepburn"]) for t in _KAKASI.convert(text))


def _word_tokens(word: str, vocab: Dict[str, int], lang: str) -> List[int]:
    global _UROMAN
    w = unicodedata.normalize("NFKC", word).lower()
    w = re.sub(r"[^\w']|_|\d", " ", w).strip()
    if not w:
        return []
    if lang == "ja":
        rom = _romanize_ja(w).lower()
    else:
        if _UROMAN is None:
            from uroman import Uroman
            _UROMAN = Uroman()
        rom = _UROMAN.romanize_string(w, lcode=_ISO3.get(lang)).lower()
    return [vocab[c] for c in rom if ("a" <= c <= "z" or c == "'") and c in vocab]


def align_lyric_lines(audio_path: str, lines: List[str], language: str) -> Optional[List[List[Dict[str, Any]]]]:
    """
    Returns, for every input line, its words as {"word", "start", "end", "score"}
    (a word with nothing pronounceable, e.g. "-", is omitted). Returns None when
    alignment fails, so callers can fall back.
    """
    lang = (language or "en").lower().split("-")[0]
    try:
        import torch
        import torchaudio.functional as AF

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model, vocab, blank = _load_model(device)
        wav = torch.from_numpy(_load_audio_16k(audio_path)).to(device, model.dtype)
        emissions, stride_s = _emissions(model, wav)
        star = emissions.size(1) - 1

        targets = [star]
        words = []  # (line_idx, word_text, token_count)
        for l_idx, line in enumerate(lines):
            for w in line.split():
                toks = _word_tokens(w, vocab, lang)
                words.append((l_idx, w, len(toks)))
                if toks:
                    targets += toks + [star]

        if len(targets) <= 1:
            return None

        path, scores = AF.forced_align(
            emissions.unsqueeze(0), torch.tensor([targets], dtype=torch.int32), blank=blank)
        spans = AF.merge_tokens(path[0], scores[0].exp(), blank=blank)
        if len(spans) != len(targets):
            raise RuntimeError(f"token spans {len(spans)} != targets {len(targets)}")

        result: List[List[Dict[str, Any]]] = [[] for _ in lines]
        pos = 1  # skip leading <star>
        for l_idx, w, n in words:
            if n == 0:
                continue
            first, last = spans[pos], spans[pos + n - 1]
            prev_end = spans[pos - 1].end
            next_start = spans[pos + n].start
            # Half of the blank gap on each side belongs to the word (CTC spikes are short)
            start_f = first.start - (first.start - prev_end) / 2
            end_f = last.end + (next_start - last.end) / 2
            word_spans = spans[pos:pos + n]
            result[l_idx].append({
                "word": w,
                "start": round(start_f * stride_s, 3),
                "end": round(end_f * stride_s, 3),
                "score": round(float(np.mean([s.score for s in word_spans])), 3),
            })
            pos += n + 1  # word tokens + following <star>

        timed = sum(len(r) for r in result)
        print(f"[MMS Align] [OK] {_t('mms.aligned', words=timed, lines=len(lines))}", flush=True)
        return result
    except Exception as e:
        print(f"[MMS Align WARNING] {_t('mms.failed', error=e)}", flush=True)
        return None
