"""No provider calls: speech markers, low-level breath-like edges and real FFmpeg."""
import io
import pytest
from pydub import AudioSegment
from pydub.generators import Sine
from app import audio
from test_workflow import client, upload, wav_bytes


def tone(hz, ms, gain=-18, rate=48000):
    return Sine(hz, sample_rate=rate).to_audio_segment(duration=ms).apply_gain(gain)


def test_no_source_context_or_fractional_tail_consumed_on_consecutive_edits(tmp_path):
    source = tone(190, 6000) + tone(110, 173, -42)
    # Explicitly add a fractional-ms tail; the former pydub [end:] lost it.
    source = source + tone(110, 1, -42).get_sample_slice(0, 17)
    src, one, two, clip = [tmp_path / n for n in ('source.wav','one.wav','two.wav','clip.wav')]
    source.export(src, format='wav')
    replacement = tone(235, 1000); replacement.export(clip, format='wav')
    duration = audio.splice(src, clip, 1, 2, one)
    first = AudioSegment.from_wav(one)
    assert first[:1000].raw_data == source[:1000].raw_data
    assert first.get_sample_slice(96000).raw_data == source.get_sample_slice(96000).raw_data
    assert first[1000:2000].raw_data == replacement.raw_data
    assert duration == source.duration_seconds
    audio.splice(one, clip, 3, 4, two)
    second = AudioSegment.from_wav(two)
    assert second[:3000].raw_data == first[:3000].raw_data
    assert second.get_sample_slice(192000).raw_data == first.get_sample_slice(192000).raw_data
    assert second.duration_seconds == source.duration_seconds


def test_preview_preserves_original_edge_ambience_and_does_not_cut_provider_speech(tmp_path):
    breath = tone(110, 200, -42)
    selected = breath + tone(190,1000) + breath
    source = tmp_path / 'source.wav'; selected.export(source,format='wav')
    provider = AudioSegment.silent(duration=300,frame_rate=48000) + tone(235,800) + AudioSegment.silent(duration=400,frame_rate=48000)
    target = tmp_path / 'preview.wav'
    clip = audio.match_preview_level(provider, source, 0, 1.4, target)
    assert clip[:200].raw_data == breath.raw_data
    assert clip[-200:].raw_data == breath.raw_data
    assert len(clip) == 1240  # 800-ms voice + 2*20-ms guards + original 2*200-ms edges
    assert abs(audio.speech_level(clip[220:1020]) - audio.speech_level(selected[200:1200])) < .1
    applied = tmp_path / 'applied.wav'; audio.splice(source,target,0,1.4,applied)
    assert AudioSegment.from_wav(applied).raw_data == clip.raw_data


def test_speech_gain_ignores_different_pause_durations(tmp_path):
    voice = tone(190,1000,-20)
    source = tmp_path / 'source.wav'; voice.export(source,format='wav')
    provider = AudioSegment.silent(duration=500,frame_rate=48000) + tone(235,1000,-20) + AudioSegment.silent(duration=500,frame_rate=48000)
    clip = audio.match_preview_level(provider, source, 0, 1, tmp_path / 'preview.wav')
    assert abs(audio.speech_level(clip) - audio.speech_level(voice)) < .2
    assert len(clip) == 2000  # No donor padding: keep natural provider breaths/pauses.


def test_active_boundaries_are_warned_not_silently_moved(tmp_path):
    source=tmp_path/'source.wav'; tone(190,1000).export(source,format='wav')
    warnings = audio.continuity_warnings(source,.2,.8)
    assert len(warnings) == 2 and 'Start' in warnings[0] and 'End' in warnings[1]


def test_two_edits_preserve_the_original_between_sentence_pause(tmp_path):
    gap = tone(110,400,-42)
    source_audio = tone(190,1000) + gap + tone(190,1000)
    src, clip, one, two = [tmp_path/n for n in ('source.wav','clip.wav','one.wav','two.wav')]
    source_audio.export(src,format='wav'); tone(235,1000).export(clip,format='wav')
    audio.splice(src,clip,0,1,one)
    audio.splice(one,clip,1.4,2.4,two)
    current=AudioSegment.from_wav(two)
    assert current[1000:1400].raw_data == gap.raw_data
    assert current.duration_seconds == source_audio.duration_seconds
