import math
import asyncio
import logging
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from . import audio, delivery, fish_audio, quality
from .sessions import Preview, Session, previews, sessions

app = FastAPI(title='Tweeq', version='0.1.0')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
                   allow_methods=['GET', 'POST', 'DELETE'], allow_headers=['Content-Type'])
DATA = ROOT / 'audio'
MAX_UPLOAD = 25 * 1024 * 1024


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(status_code=422, content={'detail': 'Invalid request. Check IDs, selection timestamps, and text.'})


@app.exception_handler(ValueError)
async def audio_error(request, exc):
    return JSONResponse(status_code=400, content={'detail': str(exc)})


@app.exception_handler(fish_audio.FishError)
async def fish_error(request, exc):
    # Log fixed diagnostic categories only, never request bodies, provider bodies or credentials.
    logging.getLogger('uvicorn.error').warning('Speech generation failed: code=%s upstream_status=%s', exc.code, exc.upstream_status)
    return JSONResponse(status_code=exc.status, content={'detail': str(exc), 'error_code': exc.code,
                                                       'upstream_status': exc.upstream_status})


def get_session(sid):
    session = sessions.get(str(sid))
    if not session:
        raise HTTPException(404, 'Session expired or not found. Please upload the recording again.')
    return session


def selection(session, start, end):
    if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= session.duration):
        raise HTTPException(400, 'Select a valid portion of the recording.')
    if round(start * 1000) >= round(end * 1000):
        raise HTTPException(400, 'Select at least one millisecond of audio.')


def cleanup_allowed(session):
    return (not session.voice_model_id and session.cleanup.get('status') != 'accepted'
            and not session.quality_report.get('severe_distortion', False)
            and any(w['code'] in ('high_frequency', 'background_energy') for w in session.quality_report.get('warnings', [])))


def info(sid, session):
    original = audio.AudioSegment.from_wav(session.folder / 'original.wav')
    status = 'unavailable' if session.voice_error else ('ready' if fish_audio.configured() else 'configuration_required')
    return {'session_id': str(sid), 'name': session.name, 'duration': session.duration,
            'original_duration': original.duration_seconds,
            'sample_rate': original.frame_rate, 'channels': original.channels,
            'waveform_url': f'/api/audio/{sid}?revision={session.revision}', 'revision': session.revision,
            'voice_status': status, 'voice_error': session.voice_error,
            'quality': quality.public(session.quality_report), 'voice_prepared': bool(session.voice_model_id),
            'reference_revision': session.reference_revision,
            'cleanup_available': cleanup_allowed(session), 'cleanup_accepted': session.cleanup.get('status') == 'accepted',
            'reference': session.reference, 'reference_url': f'/api/reference/{sid}' if session.reference else None,
            'can_redo': bool(session.redo_stack),
            'edit_count': sum(e['status'] == 'applied' for e in session.history),
            'edit_history': [{k: v for k, v in e.items() if k not in ('before_file', 'before_duration', 'after_file', 'after_duration')} for e in session.history]}


@app.get('/api/health')
def health():
    return {'status': 'ok', 'fish_configured': fish_audio.configured(),
            'ffmpeg': bool(audio.binary('ffmpeg')), 'ffprobe': bool(audio.binary('ffprobe'))}


@app.post('/api/upload')
async def upload(file: UploadFile = File(...), consent: bool = Form(False)):
    if not consent:
        raise HTTPException(400, 'Confirm that you have permission to use this voice.')
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ('.mp3', '.wav'):
        raise HTTPException(400, 'Please upload an MP3 or WAV recording.')
    sid = str(uuid4())
    folder = DATA / sid
    folder.mkdir(parents=True)
    source = folder / ('uploaded' + suffix)
    try:
        size = 0
        with source.open('wb') as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, 'Recording exceeds the 25 MB upload limit.')
                out.write(chunk)
        if size == 0:
            raise HTTPException(400, 'The uploaded recording is empty.')
        recording = await run_in_threadpool(audio.convert, source, folder / 'original.wav', True)
        report = await run_in_threadpool(quality.analyze, recording)
        ref, error = await run_in_threadpool(audio.reference, recording, folder / 'reference.wav', report)
        if ref and ref['end'] - ref['start'] < 10:
            report['status'] = 'review'
            report['warnings'].append({'code': 'short_reference', 'severity': 'warning', 'intervals': [], 'message': 'Only a short suitable voice sample was found; voice similarity may be limited.', 'recommendation': 'A longer clear single-speaker recording may help.'})
        session = Session(folder, Path(file.filename).name, recording.duration_seconds, ref, error, consent)
        session.quality_report = report
        sessions[sid] = session
        return info(sid, session)
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    finally:
        await file.close()


@app.get('/api/audio/{session_id}')
def recording(session_id: UUID, version: Literal['original', 'current'] = 'current'):
    session = get_session(session_id)
    path = session.folder / ('original.wav' if version == 'original' else session.current)
    return FileResponse(path, media_type='audio/wav', headers={'Cache-Control': 'no-store'})


@app.get('/api/reference/{session_id}')
def reference(session_id: UUID):
    session = get_session(session_id)
    if not session.reference:
        raise HTTPException(400, session.voice_error)
    return FileResponse(session.folder / 'reference.wav', media_type='audio/wav')


class RegionRequest(BaseModel):
    session_id: UUID
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    revision: int | None = Field(default=None, ge=0)


class TranscribeRequest(RegionRequest):
    revision: int = Field(ge=0)


@app.post('/api/transcribe')
async def transcribe(body: TranscribeRequest):
    import io
    session = get_session(body.session_id)
    async with session.lock:
        if body.revision != session.revision:
            raise HTTPException(409, 'Recording changed. Select a segment in the current recording.')
        selection(session, body.start, body.end)
        if not session.consent:
            raise HTTPException(400, 'Confirm permission to use this voice.')
        key = (session.revision, body.start, body.end)
        cached = key in session.transcripts
        if not cached:
            def extract():
                clip = audio.AudioSegment.from_wav(session.folder / session.current)[round(body.start * 1000):round(body.end * 1000)]
                out = io.BytesIO()
                clip.export(out, format='wav')
                return out.getvalue()
            data = await run_in_threadpool(extract)
            session.transcripts[key] = await fish_audio.transcribe(data)
        return {'text': session.transcripts[key], 'cached': cached, 'revision': session.revision,
                'session_id': str(body.session_id), 'start': body.start, 'end': body.end}


class PreviewRequest(RegionRequest):
    replacement_text: str = Field(min_length=1, max_length=1000)
    reference_text: str | None = Field(default=None, max_length=2000)
    mode: Literal['correct', 'delivery'] = 'correct'
    direction: str | None = Field(default=None, max_length=400)
    segment_text: str | None = Field(default=None, max_length=1000)
    language: str | None = Field(default=None, max_length=20)
    translated_text: str | None = Field(default=None, max_length=1000)
    original_text: str | None = Field(default=None, max_length=1000)

    @field_validator('reference_text')
    @classmethod
    def optional_reference(cls, value):
        return value.strip() or None if value else None

    @field_validator('replacement_text')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('Enter the replacement text.')
        return value.strip()


async def ensure_voice(session, sid):
    # The caller holds the session lock, so concurrent previews cannot create duplicate models.
    if not session.voice_model_id:
        voice = await fish_audio.create_voice(session.folder / 'reference.wav', f'tweeq-{sid}')
        session.voice_model_id, session.voice_model_state = voice['id'], voice['state']
    for _ in range(3):
        if session.voice_model_state == 'trained':
            return session.voice_model_id
        if session.voice_model_state == 'failed':
            raise fish_audio.FishError('Voice preparation failed. Use a clearer single-speaker recording.', code='fish_voice_failed')
        await asyncio.sleep(.5)
        voice = await fish_audio.voice_state(session.voice_model_id)
        session.voice_model_state = voice['state']
    if session.voice_model_state == 'trained':
        return session.voice_model_id
    raise fish_audio.FishError('Your voice is still being prepared. Wait a moment, then preview again; the existing voice model will be reused.', 503, code='fish_voice_processing')


@app.post('/api/preview')
async def preview(body: PreviewRequest):
    sid = str(body.session_id)
    session = get_session(sid)
    async with session.lock:
        selection(session, body.start, body.end)
        if body.revision is not None and body.revision != session.revision:
            raise HTTPException(409, 'The recording has changed. Select a region in the current recording and preview again.')
        if not session.consent:
            raise HTTPException(400, 'Confirm that you have permission to use this voice.')
        if session.voice_error:
            raise HTTPException(400, session.voice_error)
        normalized_direction = None
        if body.mode == 'delivery':
            script, normalized_direction = delivery.compose(body.segment_text, body.direction, body.language, body.translated_text)
            model_used = 'drama-3'
        else:
            script = body.replacement_text
            model_used = fish_audio.correction_model()
        options = {'model': 'drama-3', 'language': body.language if body.language in delivery.LANGUAGES else None} if body.mode == 'delivery' else {}
        if not body.reference_text:
            options['reference_id'] = await ensure_voice(session, sid)
        data = await fish_audio.generate(script, session.folder / 'reference.wav', body.reference_text, **options)
        pid = str(uuid4())
        raw, path = session.folder / f'{pid}-raw.wav', session.folder / f'{pid}.wav'
        try:
            raw.write_bytes(data)
            clip = await run_in_threadpool(audio.convert, raw, path)
            if len(clip) < 50 or clip.rms == 0:
                raise fish_audio.FishError('Fish Audio returned empty or silent speech. Please try again.')
            clip = await run_in_threadpool(audio.match_preview_level, clip, session.folder / session.current,
                                           body.start, body.end, path)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            if path.exists():
                raw.rename(session.folder / f'{pid}-provider.wav')
            else:
                raw.unlink(missing_ok=True)
        item = Preview(sid, path, body.start, body.end, session.revision, mode=body.mode,
                       direction=normalized_direction, segment_text=body.segment_text if body.mode == 'delivery' else body.replacement_text,
                       model_used=model_used, language=body.language if body.mode == 'delivery' else None,
                       translated_text=body.translated_text if body.mode == 'delivery' else None)
        item.reference_revision = session.reference_revision
        item.original_text = (body.original_text or '').strip() or (body.segment_text if body.mode == 'delivery' else None)
        item.replacement_text = (body.translated_text or body.segment_text) if body.mode == 'delivery' else body.replacement_text
        previews[pid] = item
        return {'preview_id': pid, 'preview_url': f'/api/preview/{pid}', 'duration': clip.duration_seconds,
                'mode': item.mode, 'model_used': item.model_used, 'created_at': item.created_at,
                'continuity_warnings': await run_in_threadpool(audio.continuity_warnings, session.folder / session.current, body.start, body.end),
                'duration_change': clip.duration_seconds - (body.end - body.start),
                'voice_prepared': bool(session.voice_model_id)}


@app.get('/api/preview/{preview_id}')
def get_preview(preview_id: UUID):
    item = previews.get(str(preview_id))
    if not item:
        raise HTTPException(404, 'Preview not found. Generate a new replacement.')
    return FileResponse(item.path, media_type='audio/wav')


class ReplaceRequest(RegionRequest):
    preview_id: UUID
    mode: Literal['correct', 'delivery'] | None = None


@app.post('/api/replace')
async def replace(body: ReplaceRequest):
    session = get_session(body.session_id)
    async with session.lock:
        selection(session, body.start, body.end)
        item = previews.get(str(body.preview_id))
        if not item or item.session_id != str(body.session_id):
            raise HTTPException(400, 'This preview does not belong to this session.')
        if item.used or item.revision != session.revision or item.reference_revision != session.reference_revision:
            raise HTTPException(409, 'The recording has changed. Generate a new preview.')
        if body.revision is not None and body.revision != session.revision:
            raise HTTPException(409, 'The recording has changed. Generate a new preview.')
        if body.mode is not None and body.mode != item.mode:
            raise HTTPException(409, 'Editing mode changed since preview. Generate a new preview.')
        if abs(item.start - body.start) > 0.000001 or abs(item.end - body.end) > 0.000001:
            raise HTTPException(409, 'Selection changed since preview. Generate a new preview.')
        name = f'corrected-{session.revision + 1}.wav'
        duration = await run_in_threadpool(audio.splice, session.folder / session.current, item.path,
                                          body.start, body.end, session.folder / name)
        session.history.append({'number': len(session.history) + 1, 'mode': item.mode,
            'original_text': item.original_text, 'replacement_text': item.replacement_text, 'direction': item.direction,
            'start': body.start, 'end': body.end, 'status': 'applied', 'revision': session.revision + 1,
            'after_file': name, 'after_duration': duration,
            'created_at': datetime.now(timezone.utc).isoformat(), 'before_file': session.current, 'before_duration': session.duration})
        session.redo_stack.clear()
        session.transcripts.clear()
        session.current, session.duration = name, duration
        session.revision += 1
        item.used = True
        return info(body.session_id, session)


class UndoRequest(BaseModel):
    revision: int = Field(ge=0)


@app.post('/api/cleanup/{session_id}')
async def preview_cleanup(session_id: UUID, body: UndoRequest):
    session = get_session(session_id)
    async with session.lock:
        if body.revision != session.revision:
            raise HTTPException(409, 'Recording changed. Refresh before comparing cleanup.')
        if not cleanup_allowed(session):
            raise HTTPException(400, 'Cleanup is optional for background-noise indicators before voice setup. If your voice is already prepared, finish this session and upload again to compare cleanup.')
        if not session.cleanup or session.cleanup.get('revision') != session.revision:
            path = session.folder / 'cleanup.wav'
            cleaned = await run_in_threadpool(audio.gentle_cleanup, session.folder / 'original.wav', path)
            report = await run_in_threadpool(quality.analyze, cleaned)
            ref, error = await run_in_threadpool(audio.reference, cleaned, session.folder / 'cleanup-reference.wav', report)
            session.cleanup = {'id': str(uuid4()), 'revision': session.revision, 'reference': ref,
                               'error': error, 'quality': report, 'status': 'pending'}
        session.cleanup['status'] = 'pending'
        return {'cleanup_id': session.cleanup['id'], 'cleaned_url': f'/api/cleanup/{session_id}?candidate={session.cleanup["id"]}',
                'can_accept': bool(session.cleanup['reference']), 'quality': quality.public(session.cleanup['quality']),
                'error': session.cleanup['error']}


@app.get('/api/cleanup/{session_id}')
def get_cleanup(session_id: UUID, candidate: UUID):
    session = get_session(session_id)
    if session.cleanup.get('id') != str(candidate):
        raise HTTPException(404, 'Cleanup preview not found.')
    return FileResponse(session.folder / 'cleanup.wav', media_type='audio/wav', headers={'Cache-Control': 'no-store'})


class CleanupChoice(UndoRequest):
    cleanup_id: UUID
    accept: bool


@app.post('/api/cleanup/{session_id}/choice')
async def choose_cleanup(session_id: UUID, body: CleanupChoice):
    session = get_session(session_id)
    async with session.lock:
        candidate = session.cleanup
        if candidate.get('id') != str(body.cleanup_id):
            raise HTTPException(404, 'Cleanup preview not found.')
        if body.accept and (body.revision != session.revision or candidate.get('revision') != session.revision):
            raise HTTPException(409, 'Cleanup preview is outdated. Compare again before choosing.')
        if body.accept and session.voice_model_id:
            raise HTTPException(409, 'Voice is already prepared. Upload again to compare cleanup without replacing the cached voice.')
        if candidate.get('status') == 'accepted':
            raise HTTPException(409, 'This cleanup was already accepted.')
        if body.accept:
            if not candidate.get('reference'):
                raise HTTPException(400, candidate.get('error') or 'No suitable cleaned sample was found. Rerecord instead.')
            await run_in_threadpool(shutil.copyfile, session.folder / 'cleanup-reference.wav', session.folder / 'reference.wav')
            session.reference, session.voice_error = candidate['reference'], None
            session.reference_revision += 1
            candidate['status'] = 'accepted'
        else:
            candidate['status'] = 'rejected'
        # Original, Current, audio revision, transcripts and edit history are untouched.
        return info(session_id, session)


@app.post('/api/undo/{session_id}')
async def undo(session_id: UUID, body: UndoRequest):
    session = get_session(session_id)
    async with session.lock:
        if body.revision != session.revision:
            raise HTTPException(409, 'The recording has changed. Refresh the current recording before undoing.')
        item = next((e for e in reversed(session.history) if e['status'] == 'applied'), None)
        if not item:
            raise HTTPException(400, 'There are no applied edits to undo.')
        session.current, session.duration = item['before_file'], item['before_duration']
        item['status'] = 'undone'
        session.redo_stack.append(item)
        session.transcripts.clear()
        # Keep revision monotonic: old previews and cached audio must never become valid again.
        session.revision += 1
        return info(session_id, session)


@app.post('/api/redo/{session_id}')
async def redo(session_id: UUID, body: UndoRequest):
    session = get_session(session_id)
    async with session.lock:
        if body.revision != session.revision:
            raise HTTPException(409, 'Recording changed. Refresh before redoing.')
        if not session.redo_stack:
            raise HTTPException(400, 'There are no edits to redo.')
        item = session.redo_stack.pop()
        session.current, session.duration = item['after_file'], item['after_duration']
        item['status'] = 'applied'
        session.transcripts.clear()
        session.revision += 1
        return info(session_id, session)


@app.get('/api/export/{session_id}')
async def export(session_id: UUID):
    session = get_session(session_id)
    async with session.lock:
        if session.current == 'original.wav':
            raise HTTPException(400, 'Replace a segment before exporting the corrected recording.')
        path = session.folder / f'export-{session.revision}.mp3'
        if not path.exists():
            await run_in_threadpool(audio.export_mp3, session.folder / session.current, path)
        return FileResponse(path, media_type='audio/mpeg', filename='tweeq-corrected.mp3')
