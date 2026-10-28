import io
import random
import pytest
from pydub import AudioSegment
from pydub.generators import Sine, WhiteNoise
from app import audio, quality
from test_workflow import client, upload


def voice(ms=12000,gain=-18):
    return Sine(220,sample_rate=16000).to_audio_segment(duration=ms).apply_gain(gain)


def test_quality_precedes_selection_avoids_noise_clipping_and_long_pause(tmp_path):
    random.seed(4)
    noise=WhiteNoise(sample_rate=16000).to_audio_segment(duration=10000).apply_gain(-16)
    clipped=voice(3000,15)
    recording=noise+voice()+AudioSegment.silent(duration=2500,frame_rate=16000)+clipped
    report=quality.analyze(recording)
    codes={w['code'] for w in report['warnings']}
    assert {'high_frequency','clipping','long_quiet'} <= codes
    region,error=audio.reference(recording,tmp_path/'reference.wav',report)
    assert not error and 10 <= region['start'] and region['end'] <= 22
    saved=AudioSegment.from_wav(tmp_path/'reference.wav')
    expected=recording[int(region['start']*1000):int(region['end']*1000)].set_channels(1).set_frame_rate(44100)
    assert saved.raw_data == expected.raw_data


def test_hum_and_quiet_are_indicators_not_source_or_speaker_claims(tmp_path):
    hum=Sine(60,sample_rate=16000).to_audio_segment(duration=12000).apply_gain(-18)
    report=quality.analyze(hum)
    assert 'low_tone' in {w['code'] for w in report['warnings']}
    assert audio.reference(hum,tmp_path/'hum.wav',report)[0] is None
    quiet=quality.analyze(voice(gain=-42))
    assert 'quiet_speech' in {w['code'] for w in quiet['warnings']}
    assert quality.select(quiet,12) is not None


def test_spikes_severe_distortion_and_short_fallback(tmp_path):
    source=voice(16000)
    source=source.overlay(voice(100,0),position=3000).overlay(voice(100,0),position=10000)
    report=quality.analyze(source)
    assert 'spikes' in {w['code'] for w in report['warnings']}
    region,error=audio.reference(voice(6500),tmp_path/'short.wav')
    assert not error and region['end']-region['start']==6
    distorted=voice(12000,25)
    report=quality.analyze(distorted)
    assert report['severe_distortion']
    assert audio.reference(distorted,tmp_path/'bad.wav',report)[0] is None


def test_local_reference_duration_candidates_not_padded(tmp_path):
    source=voice(35000); report=quality.analyze(source)
    short,_=audio.reference(source,tmp_path/'10.wav',report)
    long,_=audio.reference(source,tmp_path/'30.wav',report,seconds=30)
    assert short['end']-short['start']==10 and long['end']-long['start']==30
    assert len(AudioSegment.from_wav(tmp_path/'30.wav'))==30000
    assert quality.select(quality.analyze(voice(12000)),12,20) is None


def test_upload_quality_report_is_local_and_omits_frame_internals(client,monkeypatch):
    async def forbidden(*args,**kw):
        raise AssertionError('Upload quality checks must not call Fish')
    from app import fish_audio
    monkeypatch.setattr(fish_audio,'create_voice',forbidden)
    out=io.BytesIO();voice().export(out,format='wav')
    response=upload(client,out.getvalue()).json()
    assert response['quality']['warnings'] and '_frames' not in response['quality']
    assert not response['voice_prepared'] and response['reference']


def test_multiple_clean_candidates_are_separate_nonoverlapping_clips():
    source=voice(12000)+voice(100,0)+voice(12000)
    report=quality.analyze(source)
    report['_frames'][120]['bad']=True  # A manually excluded interval, as a quality indicator would produce.
    plan=quality.comparison_regions(report,source.duration_seconds)
    assert len(plan['long'])==2
    a,b=sorted(plan['long'],key=lambda x:x['start'])
    assert a['end']<=b['start']
    assert a['end']-a['start']==pytest.approx(10)
    assert b['end']-b['start']==pytest.approx(10)
