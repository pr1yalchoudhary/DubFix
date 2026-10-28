"""Prepare local reference A/B candidates. This command has NO provider client."""
import argparse
import json
from pathlib import Path
from app import audio, quality


def prepare(source, output):
    if source.resolve().parent == output.resolve():
        raise ValueError('Use a separate output folder so the source cannot be overwritten.')
    output.mkdir(parents=True,exist_ok=True)
    recording = audio.convert(source,output/'decoded-original.wav',uploaded=True)
    report = quality.analyze(recording)
    plan = quality.comparison_regions(report,recording.duration_seconds)
    manifest = {'source': str(source.resolve()), 'quality':quality.public(report), 'candidates': {},
                'default_changed':False, 'paid_requests_made':0,
                'trial': 'Compare two private cloned voices using the same authorized speaker, exact script, model and quality settings. Change only sample choice/duration. Obtain separate approval before each model creation and each TTS request. Then human-listen blind for similarity, accent, naturalness and artifacts before changing defaults.'}
    for name, regions in plan.items():
        files=[]
        for i, region in enumerate(regions):
            path=output/f'{name}-{i+1}.wav'
            recording[round(region['start']*1000):round(region['end']*1000)].set_channels(1).set_frame_rate(44100).set_sample_width(2).export(path,format='wav')
            files.append({'path':str(path.resolve()),**region})
        manifest['candidates'][name]=files
    # Cleanup is another local comparison, never a default pipeline decision.
    cleaned = audio.gentle_cleanup(output/'decoded-original.wav',output/'gentle-cleanup.wav')
    for i, region in enumerate(plan['short']):
        cleaned[round(region['start']*1000):round(region['end']*1000)].set_channels(1).set_frame_rate(44100).set_sample_width(2).export(output/f'cleanup-matched-{i+1}.wav',format='wav')
    clean_report=quality.analyze(cleaned)
    region,error=audio.reference(cleaned,output/'cleanup-selected.wav',clean_report)
    manifest['cleanup']={'quality':quality.public(clean_report),'reference':region,'error':error,
                         'accepted':False, 'note':'Listen to raw/cleaned samples; lower noise indicators do not establish better voice similarity.'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    manifest=prepare(args.source,args.output)
    print(json.dumps({'quality':manifest['quality'],'candidates':manifest['candidates'],'paid_requests_made':0},indent=2))
