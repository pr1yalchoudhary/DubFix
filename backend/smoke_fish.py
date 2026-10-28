"""Opt-in real Fish Audio smoke test; reads the key only from backend/.env.

Run from backend: python smoke_fish.py --audio path.wav --consent
Uses the same extracted reference as the app; automatic private voice setup needs no manual transcript.
"""
import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')
from app import audio, delivery, fish_audio
from app.main import ensure_voice
from app.sessions import Session


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', required=True, type=Path)
    parser.add_argument('--transcript', help='Optional legacy inline-reference transcript; omit for automatic voice setup.')
    parser.add_argument('--text', default='The conference will take place on April fifth.')
    parser.add_argument('--mode', choices=['correct', 'delivery'], default='correct')
    parser.add_argument('--direction', default='excited and enthusiastic')
    parser.add_argument('--language', choices=['en', 'hi', 'es', 'fr'])
    parser.add_argument('--consent', action='store_true', help='Confirm this is your voice or you have the speaker’s permission.')
    args = parser.parse_args()
    if not args.consent:
        parser.error('Explicit speaker consent is required (--consent).')
    if not fish_audio.configured():
        parser.error('Set FISH_AUDIO_API_KEY in backend/.env first.')
    folder = Path(__file__).parent / 'audio' / 'smoke-test'
    folder.mkdir(parents=True, exist_ok=True)
    recording = audio.convert(args.audio, folder / 'original.wav', True)
    interval, error = audio.reference(recording, folder / 'reference.wav')
    if error:
        parser.error(error)
    print(f'Reference interval: {interval["start"]}–{interval["end"]} seconds.')
    try:
        options = {}
        if not args.transcript:
            session = Session(folder, args.audio.name, len(recording) / 1000, interval, None, True)
            options['reference_id'] = await ensure_voice(session, 'cli-smoke')
        if args.mode == 'delivery':
            script, _ = delivery.compose(args.text, args.direction, args.language, args.text if args.language else None)
            data = await fish_audio.generate(script, folder / 'reference.wav', args.transcript, model='drama-3', language=args.language, **options)
        else:
            data = await fish_audio.generate(args.text, folder / 'reference.wav', args.transcript, **options)
        (folder / 'response.wav').write_bytes(data)
        clip = audio.convert(folder / 'response.wav', folder / 'preview.wav')
        audio.splice(folder / 'original.wav', folder / 'preview.wav', 0, min(2, len(recording) / 1000), folder / 'corrected.wav')
        audio.export_mp3(folder / 'corrected.wav', folder / 'corrected.mp3')
        print(f'Fish Audio returned {len(clip) / 1000:.2f}s of audio. Preview, corrected WAV and MP3 saved in {folder.resolve()}.')
        print('Listen to preview.wav to evaluate voice resemblance; a valid audio response alone does not verify voice quality.')
    except fish_audio.FishError as exc:
        raise SystemExit(str(exc))


if __name__ == '__main__':
    asyncio.run(main())
