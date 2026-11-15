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

# CTC onsets land ~80 ms after where people tap a syllable (measured +83 ms median
# against a hand-synced TTML), so every MMS time is pulled earlier by this much.
ONSET_SHIFT_S = 0.08
LINE_PAD_S = 0.15  # audio margin around a line window for syllable alignment

_CJK = "぀-ヿ㐀-鿿가-힣"
_CJK_CHAR = re.compile(rf"[{_CJK}]")
_KANJI = re.compile(r"[㐀-鿿]")
_UNIT_TOKEN = re.compile(rf"[{_CJK}]|(?:(?![{_CJK}])[\w'])+|[^\w\s']+")
_KANA_SMALL = set("ぁぃぅぇぉゃゅょゎっァィゥェォャュョヮッー")

_MODEL_CACHE: Dict[str, Any] = {}
_EM_CACHE: Dict[Any, Any] = {}  # only the last audio file's emissions
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


def _get_emissions(audio_path: str, model, device: str):
    import os
    import torch

    key = (os.path.abspath(audio_path), os.path.getmtime(audio_path), device)
    if key not in _EM_CACHE:
        _EM_CACHE.clear()
        wav = torch.from_numpy(_load_audio_16k(audio_path)).to(device, model.dtype)
        _EM_CACHE[key] = _emissions(model, wav)
    return _EM_CACHE[key]


def _kakasi():
    global _KAKASI
    if _KAKASI is None:
        import pykakasi
        _KAKASI = pykakasi.kakasi()
    return _KAKASI


def _romanize_ja(text: str) -> str:
    return "".join(_JA_PARTICLES.get(t["orig"], t["hepburn"]) for t in _kakasi().convert(text))


def _rom_tokens(rom: str, vocab: Dict[str, int]) -> List[int]:
    return [vocab[c] for c in rom.lower() if ("a" <= c <= "z" or c == "'") and c in vocab]


def _word_tokens(word: str, vocab: Dict[str, int], lang: str) -> List[int]:
    global _UROMAN
    w = unicodedata.normalize("NFKC", word).lower()
    w = re.sub(r"[^\w']|_|\d", " ", w).strip()
    if not w:
        return []
    if lang == "ja":
        rom = _romanize_ja(w)
    else:
        if _UROMAN is None:
            from uroman import Uroman
            _UROMAN = Uroman()
        rom = _UROMAN.romanize_string(w, lcode=_ISO3.get(lang))
    return _rom_tokens(rom, vocab)


def _plan_units(line: str, lang: str, dic) -> List[Dict[str, Any]]:
    """
    Syllable units of one line: {"text", "w" (word index), "rom" (None = romanize text)}.
    One unit per Hangul syllable / kana mora / hanzi, pyphen syllables for Latin words.
    Japanese kanji keep pykakasi's whole-token reading (今日 -> kyou) as one unit.
    Punctuation sticks to the neighbouring unit of the same word.
    """
    units: List[Dict[str, Any]] = []
    for wi, word in enumerate(line.split()):
        if lang == "ja":
            chunks = []
            for t in _kakasi().convert(word):
                if _KANJI.search(t["orig"]) or t["orig"] in _JA_PARTICLES:
                    chunks.append((t["orig"], _JA_PARTICLES.get(t["orig"], t["hepburn"])))
                else:
                    chunks.append((t["orig"], None))
        else:
            chunks = [(word, None)]

        first, lead = len(units), ""
        for text, rom in chunks:
            if rom is not None:  # atomic chunk with a known reading
                units.append({"text": lead + text, "w": wi, "rom": rom})
                lead = ""
                continue
            for tok in _UNIT_TOKEN.findall(text):
                if tok[0] in _KANA_SMALL and len(units) > first:
                    units[-1]["text"] += tok[0]
                    tok = tok[1:]
                    if not tok:
                        continue
                if not any(c.isalnum() for c in tok):
                    if len(units) > first:
                        units[-1]["text"] += tok
                    else:
                        lead += tok
                    continue
                if _CJK_CHAR.fullmatch(tok) or len(tok) <= 3:
                    parts = [tok]
                else:
                    cuts = [0] + dic.positions(tok) + [len(tok)]
                    parts = [tok[a:b] for a, b in zip(cuts, cuts[1:])]
                for p in parts:
                    units.append({"text": lead + p, "w": wi, "rom": None})
                    lead = ""
        if lead:  # word with nothing pronounceable, e.g. "-"
            units.append({"text": lead, "w": wi, "rom": None})
    return units


def _align_line_units(em, stride_s, star, blank, start_s, end_s, units) -> Optional[List[Optional[List[float]]]]:
    """Forced-align one line's units inside its own time window -> [start, end] per unit (None = untimed)."""
    import torch
    import torchaudio.functional as AF

    f0 = max(0, int((start_s - LINE_PAD_S) / stride_s))
    f1 = min(em.size(0), math.ceil((end_s + LINE_PAD_S) / stride_s))
    words: Dict[int, List[Any]] = {}
    for u_idx, u in enumerate(units):
        words.setdefault(u["w"], []).append((u_idx, u["toks"]))
    targets, layout = [star], []
    for _, us in sorted(words.items()):
        toks = [t for _, ts in us for t in ts]
        if toks:
            targets += toks + [star]
            layout.append(us)
    if len(targets) <= 1 or f1 - f0 < len(targets):
        return None

    path, scores = AF.forced_align(
        em[f0:f1].unsqueeze(0), torch.tensor([targets], dtype=torch.int32), blank=blank)
    spans = AF.merge_tokens(path[0], scores[0].exp(), blank=blank)
    if len(spans) != len(targets):
        return None

    out: List[Optional[List[float]]] = [None] * len(units)
    pos = 1
    for us in layout:
        n = sum(len(ts) for _, ts in us)
        ws = spans[pos:pos + n]
        w_start = ws[0].start - (ws[0].start - spans[pos - 1].end) / 2
        w_end = ws[-1].end + (spans[pos + n].start - ws[-1].end) / 2
        k, timed = 0, []
        for u_idx, ts in us:
            if ts:
                timed.append((u_idx, k, k + len(ts) - 1))
            k += len(ts)
        # unit boundaries sit halfway between neighbouring units' token spans
        for j, (u_idx, a, b) in enumerate(timed):
            s = w_start if j == 0 else (ws[timed[j - 1][2]].end + ws[a].start) / 2
            e = w_end if j == len(timed) - 1 else (ws[b].end + ws[timed[j + 1][1]].start) / 2
            out[u_idx] = [(f0 + s) * stride_s - ONSET_SHIFT_S, (f0 + e) * stride_s - ONSET_SHIFT_S]
        pos += n + 1
    return out


def _units_to_syllabi(times, units, start_s, end_s) -> List[Dict[str, Any]]:
    """Fill untimed units, clamp into the line, keep monotonic -> rawSyllabi dicts."""
    spans = [list(t) if t else None for t in times]
    for i, sp in enumerate(spans):
        if sp is None:
            prev_e = next((spans[j][1] for j in range(i - 1, -1, -1) if spans[j]), start_s)
            nxt_s = next((spans[j][0] for j in range(i + 1, len(spans)) if spans[j]), end_s)
            spans[i] = [prev_e, max(prev_e + 0.08, min(nxt_s, prev_e + 0.3))]
    # forward: monotonic from the line start; backward: squeeze anything past the line end
    prev = start_s
    for sp in spans:
        sp[0] = max(sp[0], prev)
        sp[1] = max(min(sp[1], end_s), sp[0] + 0.05)
        prev = sp[1]
    nxt = end_s
    for sp in reversed(spans):
        sp[1] = min(sp[1], nxt)
        sp[0] = min(sp[0], sp[1] - 0.05)
        nxt = sp[0]
    prev = start_s
    for sp in spans:  # only matters when a line is too short for its units
        sp[0] = max(sp[0], prev)
        sp[1] = max(sp[1], sp[0])
        prev = sp[1]

    syllabi = []
    for i, ((s, e), u) in enumerate(zip(spans, units)):
        last_in_word = i == len(units) - 1 or units[i + 1]["w"] != u["w"]
        syllabi.append({
            "time": int(round(s * 1000)),
            "duration": int(round((e - s) * 1000)),
            "text": u["text"] + (" " if last_in_word and i < len(units) - 1 else ""),
            "isSubSyllable": not last_in_word,
        })
    return syllabi


def align_line_syllables(audio_path: str, lines: List[Any], language: str) -> Optional[List[Optional[List[Dict[str, Any]]]]]:
    """
    Syllable timing for lines whose start/end are already known.
    lines: [(start_s, end_s, text)]. Returns, per line, rawSyllabi dicts
    ({"time", "duration", "text", "isSubSyllable"}, ms) or None when that line
    could not be aligned; returns None when MMS itself fails.
    """
    lang = (language or "en").lower().split("-")[0]
    try:
        import torch
        from syllable_aligner import get_pyphen_dic

        dic = get_pyphen_dic(lang)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model, vocab, blank = _load_model(device)
        em, stride_s = _get_emissions(audio_path, model, device)
        star = em.size(1) - 1

        result: List[Optional[List[Dict[str, Any]]]] = []
        for start_s, end_s, text in lines:
            units = _plan_units(text or "", lang, dic)
            for u in units:
                u["toks"] = _rom_tokens(u["rom"], vocab) if u["rom"] is not None else _word_tokens(u["text"], vocab, lang)
            syl = None
            if units and end_s > start_s:
                try:
                    times = _align_line_units(em, stride_s, star, blank, start_s, end_s, units)
                    if times is not None:
                        syl = _units_to_syllabi(times, units, start_s, end_s)
                except Exception:
                    syl = None
            result.append(syl)

        done = sum(1 for r in result if r)
        print(f"[MMS Align] [OK] {_t('mms.syllables_aligned', lines=done, total=len(lines))}", flush=True)
        return result
    except Exception as e:
        print(f"[MMS Align WARNING] {_t('mms.failed', error=e)}", flush=True)
        return None


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
        emissions, stride_s = _get_emissions(audio_path, model, device)
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
                "start": round(max(0.0, start_f * stride_s - ONSET_SHIFT_S), 3),
                "end": round(max(0.0, end_f * stride_s - ONSET_SHIFT_S), 3),
                "score": round(float(np.mean([s.score for s in word_spans])), 3),
            })
            pos += n + 1  # word tokens + following <star>

        timed = sum(len(r) for r in result)
        print(f"[MMS Align] [OK] {_t('mms.aligned', words=timed, lines=len(lines))}", flush=True)
        return result
    except Exception as e:
        print(f"[MMS Align WARNING] {_t('mms.failed', error=e)}", flush=True)
        return None
