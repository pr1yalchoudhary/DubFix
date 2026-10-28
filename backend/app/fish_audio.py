"""Verified Fish Audio REST adapter. No fallback voices or mock output."""
import asyncio
import os
from pathlib import Path

import httpx
import msgpack


class FishError(Exception):
    def __init__(self, message, status=502, *, code='speech_generation_failed', upstream_status=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.upstream_status = upstream_status


def configured():
    key = os.getenv('FISH_AUDIO_API_KEY', '').strip()
    return bool(key and key != 'your_fish_audio_key_here')


def correction_model():
    model = os.getenv('FISH_AUDIO_MODEL', 's2.1-pro-free')
    if model not in ('s2.1-pro-free', 's2.1-pro', 's2-pro'):
        raise FishError('Backend configuration: unsupported FISH_AUDIO_MODEL.', 503)
    return model


async def create_voice(reference: Path, title: str):
    """One private fast model; omit texts so Fish Audio recognizes the reference itself."""
    if not configured():
        raise FishError('Backend configuration: set FISH_AUDIO_API_KEY in backend/.env and restart the backend.', 503)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10)) as client:
            response = await client.post('https://api.fish.audio/model',
                headers={'Authorization': 'Bearer ' + os.environ['FISH_AUDIO_API_KEY'].strip()},
                data={'type': 'tts', 'title': title, 'train_mode': 'fast', 'visibility': 'private', 'generate_sample': 'false'},
                files={'voices': ('reference.wav', reference.read_bytes(), 'audio/wav')})
            return voice_result(response, expected=201)
    except httpx.HTTPError as exc:
        # Creation is never retried automatically: a timed-out request may have created a model.
        raise FishError('Voice setup was interrupted. Check your Fish Audio account before trying again; a private model may already exist.', code='fish_voice_connection') from exc


def voice_result(response, expected=200):
    if response.status_code != expected:
        messages = {401: 'Fish Audio rejected the loaded API key. Check backend configuration.',
                    402: 'Fish Audio credits or quota are insufficient for voice setup.',
                    403: 'Fish Audio denied access to voice setup.',
                    429: 'Fish Audio is rate limited. Wait before trying voice setup again.'}
        raise FishError(messages.get(response.status_code, 'Fish Audio could not prepare this voice reference. Check the sample and try again.'),
                        code=f'fish_voice_http_{response.status_code}', upstream_status=response.status_code)
    try:
        result = response.json()
        if not isinstance(result.get('_id'), str) or not result['_id'] or result.get('state') not in ('created', 'training', 'trained', 'failed'):
            raise ValueError()
        return {'id': result['_id'], 'state': result['state']}
    except (ValueError, AttributeError) as exc:
        raise FishError('Fish Audio returned an invalid voice-setup response.', code='fish_voice_invalid_response') from exc


async def voice_state(model_id: str):
    from urllib.parse import quote
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10)) as client:
            response = await client.get('https://api.fish.audio/model/' + quote(model_id, safe=''),
                headers={'Authorization': 'Bearer ' + os.environ['FISH_AUDIO_API_KEY'].strip()})
            return voice_result(response)
    except httpx.HTTPError as exc:
        raise FishError('Could not check voice preparation. Wait a moment and preview again.', code='fish_voice_status_connection') from exc


async def generate(text: str, reference: Path, transcript: str | None = None, *, model=None, language=None, reference_id=None) -> bytes:
    if not configured():
        raise FishError('Backend configuration: set FISH_AUDIO_API_KEY in backend/.env and restart the backend.', 503)
    model = correction_model() if model is None else model
    if model not in ('s2.1-pro-free', 's2.1-pro', 's2-pro', 'drama-3'):
        raise FishError('Backend configuration: unsupported speech model.', 503)
    delivery = model == 'drama-3'
    unavailable = 'Drama 3 is currently unavailable. Please check your Fish Audio API access and try again.'
    failure = "We couldn't generate this performance. Try simplifying the direction or generating another take."
    request = {'text': text, 'format': 'wav', 'sample_rate': 44100, 'latency': 'normal'}
    if reference_id:
        request['reference_id'] = reference_id
    elif transcript and transcript.strip():
        request['references'] = [{'audio': reference.read_bytes(), 'text': transcript}]
    else:
        raise FishError('Voice reference is not ready. Prepare the voice before generating speech.', code='fish_voice_not_ready')
    if delivery and language:
        request['language'] = language  # Normalization hint only; never translates the script.
    payload = msgpack.packb(request, use_bin_type=True)
    headers = {'Authorization': 'Bearer ' + os.environ['FISH_AUDIO_API_KEY'].strip(),
               'Content-Type': 'application/msgpack', 'model': model}
    messages = {
        400: 'Fish Audio rejected the text or reference sample. Check the reference transcript and recording.',
        401: 'Backend configuration: Fish Audio credentials are invalid.',
        402: 'Fish Audio credits or quota are insufficient. Check your Fish Audio account.',
        403: 'Fish Audio denied access to this model or voice.',
        422: 'Fish Audio rejected the reference sample or request parameters.',
        429: 'Fish Audio is rate limited. Wait a moment and try again.',
    }
    if delivery:
        messages.update({400: failure, 403: unavailable, 404: unavailable, 422: failure,
                         502: unavailable, 503: unavailable, 504: unavailable})
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10)) as client:
        for attempt in range(2):
            try:
                async with client.stream('POST', 'https://api.fish.audio/v1/tts', content=payload, headers=headers) as response:
                    status = response.status_code
                    if status in (429, 502, 503, 504) and attempt == 0:
                        await asyncio.sleep(1)
                        continue
                    if status != 200:
                        raise FishError(messages.get(status, failure if delivery else 'Speech generation is temporarily unavailable. Please try again.'), 429 if status == 429 else 502,
                                        code=f'fish_http_{status}', upstream_status=status)
                    chunks, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > 25 * 1024 * 1024:
                            raise FishError('Generated audio exceeded the size limit. Use shorter replacement text.')
                        chunks.append(chunk)
                    data = b''.join(chunks)
                    if len(data) < 44 or data[:4] not in (b'RIFF', b'RF64'):
                        raise FishError(failure if delivery else 'Fish Audio returned empty or invalid WAV audio. Please try again.', code='fish_invalid_audio')
                    return data
            except httpx.ConnectError as exc:
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                raise FishError('Cannot connect to Fish Audio. Check the backend network connection.', code='fish_connection_failed') from exc
            except httpx.TimeoutException as exc:
                # Do not retry ambiguous timeouts: generation may already have consumed credits.
                raise FishError('Performance generation is taking longer than expected. Please try again.' if delivery else 'Fish Audio timed out. Please try again; the request may have consumed credits.', 504, code='fish_timeout') from exc
            except httpx.HTTPError as exc:
                raise FishError('The connection to Fish Audio was interrupted. Please try again.', code='fish_stream_interrupted') from exc
    raise FishError('Speech generation is temporarily unavailable.')


async def transcribe(data: bytes):
    """One ASR attempt; no retries or paid model fallback."""
    import re
    if not configured():
        raise FishError('Configure FISH_AUDIO_API_KEY and restart the backend.', 503)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10)) as client:
            response = await client.post('https://api.fish.audio/v1/asr',
                headers={'Authorization': 'Bearer ' + os.environ['FISH_AUDIO_API_KEY'].strip(), 'model': 'transcribe-1-pro'},
                files={'audio': ('selection.wav', data, 'audio/wav')},
                data={'ignore_timestamps': 'true', 'diarize': 'false', 'tag_audio_events': 'false'})
        if response.status_code != 200:
            raise FishError('Selected speech could not be detected. Check Fish Audio credentials, credits and transcribe-1-pro access, or enter the words manually.',
                code=f'fish_asr_http_{response.status_code}', upstream_status=response.status_code)
        result = response.json()
        text = result.get('text')
        if not isinstance(text, str):
            raise ValueError()
        text = re.sub(r'<\|speaker:\d+\|>', '', text).strip()
        if not text or len(text) > 1000:
            raise ValueError()
        return text
    except httpx.HTTPError as exc:
        raise FishError('Speech detection was interrupted. Enter the words manually, or retry explicitly; the request may have consumed credits.', code='fish_asr_connection') from exc
    except (ValueError, AttributeError) as exc:
        raise FishError('No usable speech was detected. Adjust the selection or enter the words manually.', code='fish_asr_invalid_response') from exc
