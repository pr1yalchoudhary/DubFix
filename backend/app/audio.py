"""Local decoding, reference extraction, and non-destructive splicing."""
import json
import os
import shutil
import subprocess
from pathlib import Path

from pydub import AudioSegment
from pydub.silence import detect_leading_silence

MAX_SECONDS = 15 * 60


def binary(name):
    configured = os.getenv(name.upper() + '_PATH')
    local = Path(__file__).resolve().parents[2] / '.tools' / 'ffmpeg' / (name + '.exe')
    return configured or shutil.which(name) or (str(local) if local.exists() else None)


def run(args):
    try:
        return subprocess.run(args, check=True, capture_output=True, timeout=90,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except FileNotFoundError as exc:
        raise ValueError('FFmpeg and ffprobe must be installed on the backend.') from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError('Audio could not be processed. Use a valid MP3 or WAV recording.') from exc


def probe(path):
    exe = binary('ffprobe')
    if not exe:
        raise ValueError('ffprobe is missing. Install FFmpeg and ffprobe, then restart the backend.')
    data = json.loads(run([exe, '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)]).stdout)
    stream = next((s for s in data['streams'] if s.get('codec_type') == 'audio'), None)
    if not stream:
        raise ValueError('This file does not contain an audio track.')
    return float(data['format'].get('duration', stream.get('duration', 0))), stream


def convert(source, target, uploaded=False):
    duration, stream = probe(source)
    if uploaded and stream.get('codec_name') not in ('mp3', 'pcm_s16le', 'pcm_s24le', 'pcm_s32le', 'pcm_f32le', 'pcm_u8', 'pcm_f64le'):
        raise ValueError('Please upload an MP3 or PCM WAV recording.')
    if not 0 < duration <= MAX_SECONDS:
        raise ValueError('Recordings must be between 0 and 15 minutes long.')
    exe = binary('ffmpeg')
    if not exe:
        raise ValueError('FFmpeg is missing. Install it and restart the backend.')
    # Keep the recording's channel layout and time base. Provider clips still decode to mono 44.1 kHz.
    output_format = [] if uploaded else ['-ac', '1', '-ar', '44100']
    run([exe, '-y', '-v', 'error', '-i', str(source), '-vn', '-t', str(MAX_SECONDS),
         *output_format, '-c:a', 'pcm_s16le', str(target)])
    return AudioSegment.from_wav(target)


def reference(recording, target, report=None, seconds=10):
    from . import quality
    report = quality.analyze(recording) if report is None else report
    region = quality.select(report, recording.duration_seconds, seconds)
    if region is None and seconds == 10:
        # Official guidance aims for >=10 s, but shorter clean clips can be tried
        # with an explicit warning when there is no suitable full-length window.
        for shorter in (8, 6, 5):
            region = quality.select(report, recording.duration_seconds, shorter)
            if region:
                break
    if region is None:
        return None, 'Not enough suitable speech for a voice sample. Upload a clearer single-speaker recording; severe distortion should be rerecorded.'
    clip = recording[round(region['start'] * 1000):round(region['end'] * 1000)].set_channels(1).set_frame_rate(44100).set_sample_width(2)
    clip.export(target, format='wav')
    return region, None


def splice(source, replacement, start, end, target):
    recording = AudioSegment.from_wav(source)
    clip = AudioSegment.from_wav(replacement)
    # Boundaries use the same millisecond rounding as preview/ASR. Preserve every
    # frame outside the selected interval, including a fractional-ms final tail.
    first = int(round(start * 1000) * recording.frame_rate / 1000)
    last = int(round(end * 1000) * recording.frame_rate / 1000)
    before = recording.get_sample_slice(0, first)
    after = recording.get_sample_slice(last)
    # All blending was approved in the preview. Overlapping source context here
    # used to consume 100 ms per edit and could cut the preceding word/breath.
    result = before + clip + after
    result.export(target, format='wav')
    return result.duration_seconds


def speech_level(clip):
    """Median active 20-ms energy; pauses must not determine speech gain."""
    import statistics
    levels = [clip[t:t + 20].dBFS for t in range(0, len(clip) - 19, 20)]
    finite = [level for level in levels if level > -60]
    if not finite:
        return None
    threshold = max(-45, max(finite) - 25)
    active = [level for level in finite if level > threshold]
    return statistics.median(active) if active else None


def quiet_edges(clip, threshold=-38, limit=500):
    """Only inspect bounded edge padding, never search through a word."""
    lead = min(limit, detect_leading_silence(clip[:limit], threshold, 5))
    tail = min(limit, detect_leading_silence(clip[-limit:].reverse(), threshold, 5))
    return lead, tail


def continuity_warnings(source, start, end):
    recording = AudioSegment.from_wav(source)
    first, last = round(start * 1000), round(end * 1000)
    warnings = []
    # This is an energy warning, not a claim that a phoneme has been identified.
    for label, point in (('Start', first), ('End', last)):
        edge = recording[max(0, point - 10):min(len(recording), point + 10)]
        if edge.rms and edge.dBFS > -35:
            warnings.append(f'{label} is in audible audio. Listen for a cut word or breath; select a quieter gap and preview again if needed.')
    return warnings


def match_preview_level(clip, source, start, end, target):
    """Prepare continuity once before approval; Apply inserts this exact preview."""
    selected = AudioSegment.from_wav(source)[round(start * 1000):round(end * 1000)]
    clip = clip.set_frame_rate(selected.frame_rate).set_channels(selected.channels).set_sample_width(selected.sample_width)
    original_level, generated_level = speech_level(selected), speech_level(clip)
    if original_level is not None and generated_level is not None:
        clip = clip.apply_gain(max(-12, min(12, original_level - generated_level)))
    if clip.max_dBFS > -1:
        clip = clip.apply_gain(-1 - clip.max_dBFS)

    # Keep edge room tone/soft breaths from INSIDE the selected interval. A donor
    # must contain at least 40 ms of low energy. Never trim at a voiced threshold:
    # only replace near-silent provider padding (< -50 dBFS), with a 20-ms guard.
    left, right = quiet_edges(selected)
    provider_left, provider_right = quiet_edges(clip, threshold=-50)
    use_left = left >= 40
    use_right = right >= 40
    if left + right >= len(selected) - 40:
        use_left = use_right = False
    trim_left = max(0, provider_left - 20) if use_left else 0
    trim_right = max(0, provider_right - 20) if use_right else 0
    if trim_left + trim_right >= len(clip) - 50:
        trim_left = trim_right = 0
    core = clip.get_sample_slice(int(trim_left * clip.frame_rate / 1000),
                                 int(clip.frame_count()) - int(trim_right * clip.frame_rate / 1000))
    # Short ramps at generated edges only; no source samples or time are consumed.
    # Source edge padding is copied verbatim, including its low-level breaths.
    # Frame-based ramps avoid pydub's ms fade slicing losing a frame at 44.1 kHz.
    samples = core.get_array_of_samples()
    frames = int(core.frame_count())
    fade_frames = min(core.frame_rate * 5 // 1000, frames // 2)
    for i in range(fade_frames):
        gain = i / max(1, fade_frames - 1)
        for channel in range(core.channels):
            left_index = i * core.channels + channel
            right_index = (frames - 1 - i) * core.channels + channel
            samples[left_index] = int(samples[left_index] * gain)
            samples[right_index] = int(samples[right_index] * gain)
    core = core._spawn(samples.tobytes())
    clip = (selected[:left] if use_left else clip[:0]) + core + (selected[-right:] if use_right else clip[:0])
    clip.export(target, format='wav')
    return clip


def export_mp3(source, target):
    run([binary('ffmpeg') or 'ffmpeg', '-y', '-v', 'error', '-i', str(source),
         '-codec:a', 'libmp3lame', '-b:a', '192k', str(target)])


def gentle_cleanup(source, target):
    """Optional candidate only. Never overwrites Original or Current."""
    run([binary('ffmpeg') or 'ffmpeg', '-y', '-v', 'error', '-i', str(source),
         '-af', 'afftdn=nr=6:nf=-45', '-c:a', 'pcm_s16le', str(target)])
    return AudioSegment.from_wav(target)
