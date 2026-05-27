"""Multi-stage video/audio transcription pipeline."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile
import time

import requests
from google.genai import types as gemini_types

from config import (
    GCP_PROJECT_ID,
    GEMINI_TRANSCRIBE_MODEL_PRO,
    GEMINI_TRANSCRIBE_MODEL_STRONG,
    TRANSCRIPTS,
    get_gemini,
    log,
    prepare_media_part,
    retry_with_backoff,
    usage_tracker,
)
from rate_limiter import acquire as rate_limit_acquire
from schemas import TRANSCRIPTION_PROMPT, TranscriptionResult

_TRANSCRIBE_CONFIG = gemini_types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=TranscriptionResult,
    temperature=0,
    max_output_tokens=16384,
)

_DEFAULTS = {
    "text": "",
    "diarizedTranscript": [],
    "detectedLanguage": "",
    "detectedLanguageName": "",
    "isTranslated": False,
    "audioMode": "silent",
    "languagesUsed": [],
    "languagesUsedNames": [],
    "segments": [],
    "language": "",
}

_GEMINI_TRANSCRIBE_ATTEMPTS = 3


def _is_retryable_gemini_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    retryable_markers = (
        "429", "500", "502", "503", "504",
        "deadline", "timeout", "timed out",
        "temporarily unavailable", "unavailable",
        "internal error", "internal server error",
    )
    return any(marker in msg for marker in retryable_markers)


_ISO2_TO_BCP47 = {
    "en": "en-US", "ja": "ja-JP", "ko": "ko-KR", "zh": "cmn-Hans-CN",
    "fr": "fr-FR", "es": "es-ES", "de": "de-DE", "it": "it-IT",
    "pt": "pt-BR", "hi": "hi-IN", "ru": "ru-RU", "tr": "tr-TR",
    "nl": "nl-NL", "pl": "pl-PL", "sv": "sv-SE", "fi": "fi-FI",
    "el": "el-GR", "ar": "ar-XA", "id": "id-ID", "vi": "vi-VN",
    "th": "th-TH", "uk": "uk-UA", "cs": "cs-CZ", "ro": "ro-RO",
    "hu": "hu-HU", "da": "da-DK", "no": "nb-NO", "ms": "ms-MY",
}

_CHIRP3_DIAR_SUPPORTED = {
    "cmn-Hans-CN", "de-DE",
    "en-GB", "en-IN", "en-US",
    "es-ES", "es-US",
    "fr-CA", "fr-FR",
    "hi-IN", "it-IT", "ja-JP", "ko-KR", "pt-BR",
}

_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        import whisper as _whisper
        _whisper_model = _whisper.load_model("tiny")
    return _whisper_model


def detect_language(wav_path: str) -> str:
    import whisper as _whisper
    model = _get_whisper_model()
    audio = _whisper.load_audio(wav_path)
    audio = _whisper.pad_or_trim(audio)
    mel = _whisper.log_mel_spectrogram(audio).to(model.device)
    _, probs = model.detect_language(mel)
    return max(probs, key=probs.get)


def download_to_wav(url: str) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    for chunk in r.iter_content(8192):
        tmp.write(chunk)
    tmp.close()
    wav_path = tmp.name.replace(".mp4", ".wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", tmp.name, "-vn", "-ar", "16000", "-ac", "1", wav_path],
        capture_output=True,
        timeout=120,
    )
    os.unlink(tmp.name)
    return wav_path


def extract_wav_from_file(input_path: str) -> str:
    wav_path = tempfile.mktemp(suffix=".wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-vn", "-ar", "16000", "-ac", "1", wav_path],
        capture_output=True,
        timeout=120,
    )
    return wav_path


def chirp3_diarize(wav_path: str, lang_codes: list[str]) -> tuple[str, int]:
    if not GCP_PROJECT_ID:
        return "", 0
    from google.cloud.speech_v2 import SpeechClient
    from google.cloud.speech_v2.types import cloud_speech
    from google.api_core.client_options import ClientOptions

    client = SpeechClient(
        client_options=ClientOptions(api_endpoint="us-speech.googleapis.com"),
    )
    with open(wav_path, "rb") as f:
        audio = f.read()
    audio_seconds = len(audio) / (16000 * 2)
    usage_tracker.record_chirp3(audio_seconds)
    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=lang_codes,
        model="chirp_3",
        features=cloud_speech.RecognitionFeatures(
            diarization_config=cloud_speech.SpeakerDiarizationConfig(),
        ),
    )
    request = cloud_speech.RecognizeRequest(
        recognizer=f"projects/{GCP_PROJECT_ID}/locations/us/recognizers/_",
        config=config,
        content=audio,
    )
    try:
        response = client.recognize(request=request)
    except Exception as e:
        if "speaker_diarization" in str(e) and lang_codes != ["auto"]:
            log(f"  chirp3: diarization unsupported for {lang_codes}, retrying with auto")
            config = cloud_speech.RecognitionConfig(
                auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
                language_codes=["auto"],
                model="chirp_3",
                features=cloud_speech.RecognitionFeatures(
                    diarization_config=cloud_speech.SpeakerDiarizationConfig(),
                ),
            )
            request = cloud_speech.RecognizeRequest(
                recognizer=f"projects/{GCP_PROJECT_ID}/locations/us/recognizers/_",
                config=config,
                content=audio,
            )
            response = client.recognize(request=request)
        else:
            raise
    lines, spkrs = [], set()
    for result in response.results:
        alt = result.alternatives[0]
        cur_spk, cur_words = None, []
        for w in alt.words:
            spk = w.speaker_label or "?"
            spkrs.add(spk)
            if spk != cur_spk:
                if cur_words:
                    lines.append(f"[{cur_spk}] {' '.join(cur_words)}")
                cur_spk, cur_words = spk, [w.word]
            else:
                cur_words.append(w.word)
        if cur_words:
            lines.append(f"[{cur_spk}] {' '.join(cur_words)}")
    return "\n".join(lines), len(spkrs)


MIN_DIAR_SEGMENTS = 3


def _gemini_transcribe_single(gemini, part, use_model, path, cache_json, prompt=None):
    if prompt is None:
        prompt = TRANSCRIPTION_PROMPT

    last_error = None
    for attempt in range(1, _GEMINI_TRANSCRIBE_ATTEMPTS + 1):
        try:
            rate_limit_acquire("gemini", use_model)
            t0 = time.time()
            resp = gemini.models.generate_content(
                model=use_model,
                contents=[part, prompt],
                config=_TRANSCRIBE_CONFIG,
            )
            usage_tracker.record_gemini(
                "transcribe",
                resp,
                model=use_model,
                latency_ms=(time.time() - t0) * 1000,
            )
            result = json.loads(resp.text)
            break
        except json.JSONDecodeError as e:
            last_error = e
            if attempt >= _GEMINI_TRANSCRIBE_ATTEMPTS:
                raise
            log(f"  gemini transcribe retry {attempt}/{_GEMINI_TRANSCRIBE_ATTEMPTS} "
                f"for {path.name}: malformed JSON")
            time.sleep(min(2 ** attempt, 8))
        except Exception as e:
            last_error = e
            if attempt >= _GEMINI_TRANSCRIBE_ATTEMPTS or not _is_retryable_gemini_error(e):
                raise
            log(f"  gemini transcribe retry {attempt}/{_GEMINI_TRANSCRIBE_ATTEMPTS} "
                f"for {path.name}: {str(e)[:120]}")
            time.sleep(min(2 ** attempt, 8))
    else:
        raise last_error or RuntimeError("Gemini transcription failed")

    for k, v in _DEFAULTS.items():
        result.setdefault(k, v)
    result.setdefault("language", result.get("detectedLanguage", ""))

    cache_json.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return result


@retry_with_backoff(max_retries=5, base_delay=3.0)
def transcribe_video(
    path: pathlib.Path,
    media_part: object | None = None,
    media_url: str | None = None,
    model: str | None = None,
) -> dict:
    empty = dict(_DEFAULTS)
    if not path.exists() and media_part is None and media_url is None:
        return empty

    cache_json = TRANSCRIPTS / (path.stem + ".json")
    if cache_json.exists():
        try:
            cached = json.loads(cache_json.read_text())
            if "diarizedTranscript" in cached:
                return cached
        except Exception:
            cache_json.unlink(missing_ok=True)

    try:
        gemini = get_gemini()
    except RuntimeError:
        return empty

    try:
        part = media_part
        if part is None:
            if path.exists():
                part = prepare_media_part(path)
            elif media_url:
                from google.genai import types as _types
                part = _types.Part.from_uri(file_uri=media_url, mime_type="video/mp4")
            else:
                return empty

        if model:
            return _gemini_transcribe_single(gemini, part, model, path, cache_json)

        diar_text = ""
        use_model = GEMINI_TRANSCRIBE_MODEL_STRONG
        wav_path = None

        if GCP_PROJECT_ID:
            try:
                if path.exists():
                    wav_path = extract_wav_from_file(str(path))
                elif media_url:
                    wav_path = download_to_wav(media_url)

                if wav_path:
                    detected_lang = detect_language(wav_path)
                    bcp47 = _ISO2_TO_BCP47.get(detected_lang, "en-US")
                    if bcp47 in _CHIRP3_DIAR_SUPPORTED:
                        lang_codes = [bcp47, "en-US"] if bcp47 != "en-US" else ["en-US"]
                    else:
                        lang_codes = ["auto"]
                    diar_text, n_spk = chirp3_diarize(wav_path, lang_codes)
                    log(f"  diarize: Chirp3 lang={detected_lang} codes={lang_codes} "
                        f"({n_spk} speakers) for {path.name}")

                    if diar_text and len(diar_text.strip().split("\n")) >= MIN_DIAR_SEGMENTS:
                        use_model = GEMINI_TRANSCRIBE_MODEL_STRONG
                    else:
                        log(f"  diarize: sparse output, falling back to Pro for {path.name}")
                        use_model = GEMINI_TRANSCRIBE_MODEL_PRO
                        diar_text = ""
            except Exception as e:
                log(f"  diarize error for {path.name}: {e}")
                use_model = GEMINI_TRANSCRIBE_MODEL_STRONG
            finally:
                if wav_path and os.path.exists(wav_path):
                    os.unlink(wav_path)

        if diar_text:
            prompt = (
                "A dedicated speaker-diarization model pre-analyzed the audio using "
                "voiceprint clustering. Each Speaker ID below is a SINGLE person — all "
                "segments with the same Speaker ID are the SAME voice. This grouping is "
                "definitive and must NOT be split across different labels.\n\n"
                "STEP 1: Decide which Speaker ID = 'ai' and which = 'creator' by voice "
                "quality. The AI/TTS voice is unnaturally smooth with consistent pitch; "
                "the creator's voice is natural with breathing and emotion.\n"
                "STEP 2: Apply that mapping to EVERY segment from that Speaker ID. "
                "Do NOT re-classify individual segments — the Speaker ID grouping is final.\n\n"
                f"DIARIZATION:\n{diar_text}\n\n" + TRANSCRIPTION_PROMPT
            )
        else:
            prompt = TRANSCRIPTION_PROMPT

        return _gemini_transcribe_single(gemini, part, use_model, path, cache_json, prompt)

    except Exception as e:
        log(f"  gemini transcribe error for {path.name}: {e}")
        raise


def transcribe(
    input_path: str | pathlib.Path | None = None,
    url: str | None = None,
    model: str | None = None,
) -> dict:
    tmp_path = None
    try:
        if input_path:
            path = pathlib.Path(input_path)
        elif url:
            tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            r = requests.get(url, stream=True, timeout=60)
            r.raise_for_status()
            for chunk in r.iter_content(8192):
                tmp.write(chunk)
            tmp.close()
            path = pathlib.Path(tmp.name)
            tmp_path = tmp.name
        else:
            raise ValueError("Either input_path or url must be provided")

        return transcribe_video(path, media_url=url, model=model)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Transcribe video/audio files")
    parser.add_argument("input", help="Path to video/audio file or URL")
    parser.add_argument("--model", help="Force a specific Gemini model")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    is_url = args.input.startswith(("http://", "https://"))
    result = transcribe(
        url=args.input if is_url else None,
        input_path=args.input if not is_url else None,
        model=args.model,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Language: {result.get('detectedLanguage', 'unknown')} "
              f"({result.get('detectedLanguageName', '')})")
        print(f"Audio mode: {result.get('audioMode', 'unknown')}")
        for seg in result.get("diarizedTranscript", []):
            print(f"  [{seg.get('speaker')}] {seg.get('text')}")
        usage_tracker.print_summary()
