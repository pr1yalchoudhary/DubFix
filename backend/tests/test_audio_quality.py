"""Local signal tests establish processing behavior, not subjective voice similarity."""
import io
from pydub import AudioSegment
from pydub.generators import Sine
from app import audio
from test_workflow import client, upload


def frequency(clip):
    data = clip.split_to_mono()[0].get_array_of_samples()
    return sum(a <= 0 < b for a, b in zip(data, data[1:])) / clip.duration_seconds


def test_preserve_48k_stereo_and_preview_pitch_through_export(client, tmp_path):
    left = Sine(190, sample_rate=48000).to_audio_segment(duration=13000).apply_gain(-18)
    right = Sine(330, sample_rate=48000).to_audio_segment(duration=13000).apply_gain(-22)
    source = AudioSegment.from_mono_audiosegments(left, right)
    out = io.BytesIO(); source.export(out, format='wav')
    uploaded = upload(client, out.getvalue()).json()
    assert uploaded['sample_rate'] == 48000 and uploaded['channels'] == 2
    original_path = tmp_path / 'original.wav'
    original_path.write_bytes(client.get(uploaded['waveform_url']).content)
    original = AudioSegment.from_wav(original_path)
    assert original.raw_data == source.raw_data
    ref = AudioSegment.from_wav(io.BytesIO(client.get(uploaded['reference_url']).content))
    assert ref.channels == 1 and ref.frame_rate == 44100
    provider = Sine(235).to_audio_segment(duration=2500).apply_gain(-14)
    preview_path = tmp_path / 'preview.wav'
    preview = audio.match_preview_level(provider, original_path, 9, 11, preview_path)
    assert preview.frame_rate == 48000 and preview.channels == 2
    assert abs(len(preview) - len(provider)) <= 1
    assert abs(frequency(preview[100:2300]) - 235) < 1
    current_path = tmp_path / 'current.wav'
    audio.splice(original_path, preview_path, 9, 11, current_path)
    current = AudioSegment.from_wav(current_path)
    assert current[:8900].raw_data == original[:8900].raw_data
    assert preview[100:2300].raw_data in current.raw_data
    assert abs(frequency(current[9200:11200]) - 235) < 1
    mp3_path = tmp_path / 'export.mp3'; audio.export_mp3(current_path, mp3_path)
    _, stream = audio.probe(mp3_path)
    assert stream['sample_rate'] == '48000' and stream['channels'] == 2


def test_reference_skips_leading_quiet_only_when_ten_seconds_remain(tmp_path):
    quiet = AudioSegment.silent(duration=1200, frame_rate=44100)
    speech = Sine(190).to_audio_segment(duration=12300).apply_gain(-18)
    source = quiet + speech
    ref, error = audio.reference(source, tmp_path / 'reference.wav')
    assert not error and ref == {'start': 1.2, 'end': 11.2}
    assert AudioSegment.from_wav(tmp_path / 'reference.wav').raw_data == source[1200:11200].raw_data
    ref, _ = audio.reference(quiet + speech[:9000], tmp_path / 'short-reference.wav')
    assert ref == {'start': .2, 'end': 10.2}
