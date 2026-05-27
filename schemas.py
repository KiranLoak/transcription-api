"""Pydantic schemas and prompts for the transcription pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DiarizedSegment(BaseModel):
    speaker: str = Field(
        ...,
        description="Speaker label: creator, ai, narrator, on-screen-ocr, person1..N, other",
    )
    text: str = Field(..., description="English translation")
    originalText: str = Field(..., description="Original language text")
    language: str = Field(..., description="ISO 639-1 code")
    languageName: str = Field(..., description="Human-readable language name")


class TranscriptionResult(BaseModel):
    text: str
    diarizedTranscript: list[DiarizedSegment]
    audioMode: Literal[
        "spoken-narration", "music-only", "music-with-lyrics", "silent", "mixed",
    ]
    detectedLanguage: str
    detectedLanguageName: str
    languagesUsed: list[str]
    languagesUsedNames: list[str]
    isTranslated: bool


TRANSCRIPTION_PROMPT = (
    "Transcribe this short-form video and produce a TranscriptionResult.\n\n"
    "SPEAKER LABELS (assign one per DiarizedSegment):\n"
    "  - 'creator'       = the real human creator. Identify by VOICE QUALITY: natural "
    "human speech with breathing, hesitation, laughter, emotion. Usually speaks the "
    "viewer's language (often English) and reacts to or prompts the AI.\n"
    "  - 'ai'            = synthetic / text-to-speech / chatbot voice. Identify by VOICE "
    "QUALITY: unnaturally smooth, consistent pitch, robotic cadence, or clearly generated "
    "speech. Often speaks in a foreign language being taught. In language-learning videos "
    "the AI character is the one giving lessons, corrections, or scripted dialogue.\n"
    "  - 'narrator'      = off-camera voiceover (a human voice not visible on camera)\n"
    "  - 'on-screen-ocr' = text that appears ON SCREEN (captions, overlays, titles, "
    "kinetic text). Use this label even when there is also spoken audio — extract on-screen "
    "text as its OWN segment(s) alongside the spoken ones.\n"
    "  - 'person1' / 'person2' / 'person3' / 'person4' / 'person5' = additional distinct "
    "people on camera, numbered in order of first appearance. Use these instead of 'other' "
    "when you can distinguish individuals.\n"
    "  - 'other'         = unattributable voice (brief background voice you cannot identify).\n\n"
    "PER-SEGMENT FIELDS:\n"
    "  - `text`         = English translation (same as originalText if already English; "
    "for on-screen-ocr, an English translation of the visible text)\n"
    "  - `originalText` = untranslated transcript in the spoken language. For on-screen-ocr, "
    "the LITERAL visible text exactly as written.\n"
    "  - `language`     = ISO 639-1 code ('en', 'es', 'ko', 'ja', 'zh', ...)\n"
    "  - `languageName` = human-readable ('English', 'Spanish', 'Korean', ...)\n\n"
    "TOP-LEVEL FIELDS:\n"
    "  - `text`            = full English transcript concatenated from all segments in order, "
    "no speaker labels\n"
    "  - `detectedLanguage` / `detectedLanguageName` = primary SPOKEN language "
    "(ignore on-screen-ocr segments for this)\n"
    "  - `languagesUsed` / `languagesUsedNames` = deduplicated lists of all ISO codes / names "
    "across segments, in matching order\n"
    "  - `isTranslated`    = true if ANY segment's language is not 'en'\n"
    "  - `audioMode` classifies what the viewer HEARS (ignore on-screen-ocr for this):\n"
    "      'spoken-narration' | 'music-only' | 'music-with-lyrics' | 'silent' | 'mixed'\n\n"
    "RULES:\n"
    "  - LIP-SYNC CHECK: When a person is visible on screen, watch their lips. If their "
    "lips are NOT moving during a spoken segment, that voice belongs to someone OFF-SCREEN "
    "(the AI app character or a narrator) — do NOT label it as 'creator'. Only label a "
    "segment 'creator' if you can see the on-screen person's lips moving in sync with the "
    "audio. If the visible person's mouth is closed or they are just reacting/listening, "
    "the voice is 'ai' or 'narrator'.\n"
    "  - VOICE CONSISTENCY: Track each distinct voice throughout the video. Once you "
    "identify a voice as 'ai' or 'creator' early on, the SAME voice must keep that label "
    "for ALL subsequent segments — including reactions, laughter, closing remarks, "
    "promotional lines, and CTAs.\n"
    "  - ALWAYS extract on-screen text as 'on-screen-ocr' segments, even when speech is present.\n"
    "  - Multiple on-camera people → use person1, person2, ... in order of first appearance. "
    "The primary creator (delivering the main content) is 'creator'.\n"
    "  - Split into separate segments when the language switches.\n"
    "  - Preserve filler words and slang in originalText; clean up only the English text.\n"
    "  - No speech AND no on-screen text → empty diarizedTranscript, empty top-level text, "
    "set audioMode accordingly, isTranslated=false."
)
