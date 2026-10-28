import io
import random
from pydub import AudioSegment
from pydub.generators import Sine, WhiteNoise
from app import audio, main
from app.sessions import sessions, previews, Preview
from uuid import uuid4
from test_workflow import client, upload


def noisy():
    random.seed(12)
    voice=Sine(220,sample_rate=16000).to_audio_segment(duration=16000).apply_gain(-20)
    noise=WhiteNoise(sample_rate=16000).to_audio_segment(duration=16000).apply_gain(-48)
    out=io.BytesIO(); voice.overlay(noise).export(out,format='wav'); return out.getvalue()


def test_cleanup_is_local_cached_explicit_and_original_unchanged(client,monkeypatch):
    result=upload(client,noisy()).json(); sid=result['session_id']
    session=sessions[sid]
    # Persistent-energy warning enables optional comparison, not automatic filtering.
    assert result['cleanup_available']
    original=client.get(f'/api/audio/{sid}?version=original').content
    original_reference=(session.folder/'reference.wav').read_bytes()
    calls=[]
    real_cleanup=audio.gentle_cleanup
    def counted(*args):
        calls.append(1);return real_cleanup(*args)
    monkeypatch.setattr(audio,'gentle_cleanup',counted)
    candidate=client.post(f'/api/cleanup/{sid}',json={'revision':0}).json()
    cleaned=client.get(candidate['cleaned_url'])
    assert cleaned.status_code==200 and candidate['can_accept']
    assert '_frames' not in candidate['quality']
    cleanclip=AudioSegment.from_wav(io.BytesIO(cleaned.content))
    oldclip=AudioSegment.from_wav(io.BytesIO(original))
    assert cleanclip.frame_count()==oldclip.frame_count()
    assert cleanclip.frame_rate==oldclip.frame_rate and cleanclip.channels==oldclip.channels
    assert (session.folder/'reference.wav').read_bytes()==original_reference
    assert client.post(f'/api/cleanup/{sid}',json={'revision':0}).json()['cleanup_id']==candidate['cleanup_id']
    assert len(calls)==1
    choice={'revision':0,'cleanup_id':candidate['cleanup_id'],'accept':False}
    rejected=client.post(f'/api/cleanup/{sid}/choice',json=choice).json()
    assert rejected['reference_revision']==0 and not rejected['cleanup_accepted']
    assert (session.folder/'reference.wav').read_bytes()==original_reference
    preview_id=str(uuid4())
    previews[preview_id]=Preview(sid,session.folder/'legacy-preview.wav',1,2,0)
    accepted=client.post(f'/api/cleanup/{sid}/choice',json={**choice,'accept':True}).json()
    assert accepted['reference_revision']==1 and accepted['cleanup_accepted']
    assert (session.folder/'reference.wav').read_bytes()==(session.folder/'cleanup-reference.wav').read_bytes()
    assert accepted['revision']==0 and accepted['edit_count']==0 and not accepted['voice_prepared']
    assert client.get(f'/api/audio/{sid}').content==original
    assert client.get(f'/api/audio/{sid}?version=original').content==original
    assert not accepted['cleanup_available']
    assert client.post('/api/replace',json={'session_id':sid,'start':1,'end':2,'preview_id':preview_id}).status_code==409


def test_cleanup_rejects_stale_selection_and_preserves_cached_voice(client):
    sid=upload(client,noisy()).json()['session_id'];session=sessions[sid]
    assert client.post(f'/api/cleanup/{sid}',json={'revision':1}).status_code==409
    candidate=client.post(f'/api/cleanup/{sid}',json={'revision':0}).json()
    session.voice_model_id='existing-private-voice'
    response=client.post(f'/api/cleanup/{sid}/choice',json={'revision':0,'cleanup_id':candidate['cleanup_id'],'accept':True})
    assert response.status_code==409 and session.voice_model_id=='existing-private-voice'
    assert session.reference_revision==0
    assert client.post(f'/api/cleanup/{sid}',json={'revision':0}).status_code==400
    assert client.post(f'/api/cleanup/{sid}/choice',json={'revision':0,'cleanup_id':candidate['cleanup_id'],'accept':False}).status_code==200
