import asyncio
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Session:
    folder: Path
    name: str
    duration: float
    reference: dict | None
    voice_error: str | None
    consent: bool
    quality_report: dict = field(default_factory=dict)
    cleanup: dict = field(default_factory=dict)
    reference_revision: int = 0
    revision: int = 0
    current: str = 'original.wav'
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    voice_model_id: str | None = None
    voice_model_state: str | None = None
    transcripts: dict = field(default_factory=dict)
    redo_stack: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)


@dataclass
class Preview:
    session_id: str
    path: Path
    start: float
    end: float
    revision: int
    used: bool = False
    mode: str = 'correct'
    direction: str | None = None
    segment_text: str | None = None
    model_used: str | None = None
    language: str | None = None
    translated_text: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reference_revision: int = 0
    original_text: str | None = None
    replacement_text: str | None = None


sessions: dict[str, Session] = {}
previews: dict[str, Preview] = {}
