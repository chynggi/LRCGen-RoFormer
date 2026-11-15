"""
Minimal i18n for backend console messages.

Language: env var LRCGEN_LANG (en / ko / de), otherwise the system locale,
otherwise English.  Usage:  t("uvr.loading_model", model=model_file)
"""

import locale
import os

SUPPORTED = ("en", "ko", "de")

MESSAGES = {
    # ── AI Studio (app.py) ────────────────────────────────────────────────────
    "studio.isolate_syllables": {
        "en": "Step 1/2: Isolating vocal track (UVR-MDX-Net) for syllable detection...",
        "ko": "1/2단계: 음절 인식을 위해 보컬 트랙 분리 중 (UVR-MDX-Net)...",
        "de": "Schritt 1/2: Isoliere Gesangsspur (UVR-MDX-Net) fuer Silben-Erkennung...",
    },
    "studio.isolate_lines": {
        "en": "Step 1/2: Isolating vocal track (UVR-MDX-Net) for precise line detection...",
        "ko": "1/2단계: 정밀한 라인 인식을 위해 보컬 트랙 분리 중 (UVR-MDX-Net)...",
        "de": "Schritt 1/2: Isoliere Gesangsspur (UVR-MDX-Net) fuer praezise Zeilen-Erkennung...",
    },
    "studio.alignment_failed": {
        "en": "Alignment failed: {error}",
        "ko": "정렬 실패: {error}",
        "de": "Alignment fehlgeschlagen: {error}",
    },
    "studio.cached_acapella": {
        "en": "Using cached acapella: {path}",
        "ko": "캐시된 아카펠라 사용 중: {path}",
        "de": "Verwende gecachtes Acapella: {path}",
    },
    "studio.acapella_ok": {
        "en": "Acapella isolated successfully -> {path}",
        "ko": "아카펠라 분리 성공 -> {path}",
        "de": "Acapella erfolgreich isoliert -> {path}",
    },
    "studio.acapella_failed": {
        "en": "Acapella separation error: {error}. Using original audio.",
        "ko": "아카펠라 분리 오류: {error}. 원본 오디오를 사용합니다.",
        "de": "Acapella-Separation Fehler: {error}. Verwende Original-Audio.",
    },
    "studio.project_save_warning": {
        "en": "Warning while saving the project: {error}",
        "ko": "프로젝트 저장 중 경고: {error}",
        "de": "Warnung beim Speichern des Projekts: {error}",
    },
    # ── UVR5 vocal separation (app.py) ────────────────────────────────────────
    "uvr.loading_model": {
        "en": "Loading model: {model}...",
        "ko": "모델 로딩 중: {model}...",
        "de": "Lade Modell: {model}...",
    },
    "uvr.starting": {
        "en": "Starting vocal isolation on: {path}...",
        "ko": "보컬 분리 시작: {path}...",
        "de": "Starte Gesangsisolation auf: {path}...",
    },
    "uvr.success": {
        "en": "Vocal isolation successful: {path}",
        "ko": "보컬 분리 성공: {path}",
        "de": "Gesangsisolation erfolgreich: {path}",
    },
    "uvr.no_output": {
        "en": "No output files found. Separator: {files}",
        "ko": "출력 파일을 찾지 못했습니다. Separator: {files}",
        "de": "Keine Ausgabedateien gefunden. Separator: {files}",
    },
    "uvr.success_output1": {
        "en": "Vocal isolation (output 1): {path}",
        "ko": "보컬 분리 (출력 1): {path}",
        "de": "Gesangsisolation (Output 1): {path}",
    },
    "uvr.failed": {
        "en": "Vocal isolation failed: {error}",
        "ko": "보컬 분리 실패: {error}",
        "de": "Gesangsisolation fehlgeschlagen: {error}",
    },
    "uvr.not_installed": {
        "en": "audio-separator could not be imported (missing package or dependency): {error}",
        "ko": "audio-separator를 불러오지 못했습니다 (패키지 또는 의존성 누락): {error}",
        "de": "audio-separator konnte nicht importiert werden (Paket oder Abhängigkeit fehlt): {error}",
    },
    # ── WhisperX / Whisper alignment (syllable_aligner.py) ───────────────────
    "wx.cached_model": {
        "en": "Using cached CTranslate2 model '{model}'...",
        "ko": "캐시된 CTranslate2 모델 '{model}' 사용 중...",
        "de": "Verwende gecachtes CTranslate2-Modell '{model}'...",
    },
    "wx.init_model": {
        "en": "Initializing CTranslate2 ('{model}', device: {device})...",
        "ko": "CTranslate2 초기화 중 ('{model}', 장치: {device})...",
        "de": "Initialisiere CTranslate2 ('{model}', Device: {device})...",
    },
    "wx.transcribing_vad": {
        "en": "Transcribing acapella with VAD...",
        "ko": "VAD로 아카펠라 전사 중...",
        "de": "Transkribiere Acapella mit VAD...",
    },
    "wx.cached_align_model": {
        "en": "Using cached CTC alignment model for language '{lang}'...",
        "ko": "언어 '{lang}'에 대해 캐시된 CTC 정렬 모델 사용 중...",
        "de": "Verwende gecachtes CTC-Alignment-Modell fuer Sprache '{lang}'...",
    },
    "wx.loading_align_model": {
        "en": "Loading phonetic CTC alignment model for language '{lang}'...",
        "ko": "언어 '{lang}'용 음성학적 CTC 정렬 모델 로딩 중...",
        "de": "Lade phonetisches CTC-Alignment-Modell fuer Sprache '{lang}'...",
    },
    "wx.align_model_failed": {
        "en": "Could not load CTC model for '{lang}': {error}",
        "ko": "'{lang}'용 CTC 모델을 불러오지 못했습니다: {error}",
        "de": "Konnte CTC Modell fuer '{lang}' nicht laden: {error}",
    },
    "wx.fallback_word_segments": {
        "en": "Falling back to word segments ({error})",
        "ko": "단어 세그먼트로 대체합니다 ({error})",
        "de": "Fallback auf Wort-Segmente ({error})",
    },
    "wx.words_aligned": {
        "en": "{count} words acoustically aligned with Wav2Vec2!",
        "ko": "Wav2Vec2로 단어 {count}개를 음향 정렬했습니다!",
        "de": "{count} Woerter akustisch mit Wav2Vec2 ausgerichtet!",
    },
    # ── MMS forced alignment (mms_aligner.py) ────────────────────────────────
    "mms.loading_model": {
        "en": "Loading MMS forced-alignment model '{model}' (device: {device})...",
        "ko": "MMS 강제 정렬 모델 '{model}' 로딩 중 (장치: {device})...",
        "de": "Lade MMS-Forced-Alignment-Modell '{model}' (Device: {device})...",
    },
    "mms.aligned": {
        "en": "{words} lyric words force-aligned across {lines} lines!",
        "ko": "가사 단어 {words}개를 {lines}줄에 걸쳐 강제 정렬했습니다!",
        "de": "{words} Liedtext-Woerter ueber {lines} Zeilen zwangsausgerichtet!",
    },
    "mms.syllables_aligned": {
        "en": "Syllables force-aligned for {lines}/{total} lines!",
        "ko": "{total}줄 중 {lines}줄의 음절을 강제 정렬했습니다!",
        "de": "Silben für {lines}/{total} Zeilen zwangsausgerichtet!",
    },
    "mms.failed": {
        "en": "MMS alignment failed, falling back to WhisperX matching: {error}",
        "ko": "MMS 정렬 실패, WhisperX 매칭으로 대체합니다: {error}",
        "de": "MMS-Alignment fehlgeschlagen, Fallback auf WhisperX-Matching: {error}",
    },
    "whisper.loading_model": {
        "en": "Loading model '{model}'...",
        "ko": "모델 '{model}' 로딩 중...",
        "de": "Lade Modell '{model}'...",
    },
    "whisper.cached_model": {
        "en": "Using cached model '{model}'...",
        "ko": "캐시된 모델 '{model}' 사용 중...",
        "de": "Verwende gecachtes Modell '{model}'...",
    },
    "whisper.transcribing": {
        "en": "Transcribing & extracting word timestamps from: {path}...",
        "ko": "전사 및 단어 타임스탬프 추출 중: {path}...",
        "de": "Transkribiere & extrahiere Wort-Timestamps aus: {path}...",
    },
    "whisper.done": {
        "en": "Done! {count} words acoustically detected.",
        "ko": "완료! 단어 {count}개를 음향으로 인식했습니다.",
        "de": "Fertig! {count} Woerter akustisch erkannt.",
    },
    "whisper.warning": {
        "en": "Warning",
        "ko": "경고",
        "de": "Warnung",
    },
    "pyphen.generating": {
        "en": "Generating syllables for {count} lines (language: {lang})...",
        "ko": "{count}개 라인의 음절 생성 중 (언어: {lang})...",
        "de": "Generiere Silben fuer {count} Zeilen (Sprache: {lang})...",
    },
}


def _detect_lang() -> str:
    env = os.environ.get("LRCGEN_LANG", "").strip().lower()
    if env[:2] in SUPPORTED:
        return env[:2]
    try:
        loc = (locale.getlocale()[0] or "").lower()   # e.g. "ko_KR", "Korean_Korea"
    except Exception:
        loc = ""
    if loc.startswith(("ko", "korean")):
        return "ko"
    if loc.startswith(("de", "german")):
        return "de"
    return "en"


LANG = _detect_lang()


def t(key: str, **kwargs) -> str:
    """Translate `key` into the active language, falling back to English."""
    entry = MESSAGES.get(key)
    if entry is None:
        return key
    text = entry.get(LANG) or entry["en"]
    return text.format(**kwargs) if kwargs else text
