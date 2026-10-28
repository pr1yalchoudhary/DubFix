"""Local signal indicators, not ASR, speaker identification or proof of intelligibility."""
import audioop
import math
import statistics

STEP = 100  # Timestamp resolution of reported intervals, in milliseconds.


def db(value):
    return 20 * math.log10(value / 32768) if value else -100.0


def runs(mask, minimum=1):
    result, start = [], None
    for i, value in enumerate([*mask, False]):
        if value and start is None:
            start = i
        elif not value and start is not None:
            if i - start >= minimum:
                result.append((start, i))
            start = None
    return result


def tonal_ratio(raw):
    samples = memoryview(raw).cast('h')
    energy = sum(v * v for v in samples)
    if not energy:
        return 0
    strongest = 0
    for hz in (50, 60, 100, 120):
        coefficient = 2 * math.cos(2 * math.pi * hz / 2000)
        a = b = 0.0
        for value in samples:
            current = value + coefficient * a - b
            b, a = a, current
        power = a * a + b * b - coefficient * a * b
        strongest = max(strongest, 2 * power / (len(samples) * energy))
    return strongest


def analyze(recording):
    mono = recording.set_channels(1).set_sample_width(2)
    small = mono.set_frame_rate(16000)
    low = mono.set_frame_rate(2000)
    frames = []
    for start in range(0, len(small), STEP):
        clip = small[start:start + STEP]
        raw = clip.raw_data
        original = recording[start:start + STEP].set_sample_width(2)
        peak = audioop.max(original.raw_data, 2)
        clipped = False
        if peak >= 32700:
            values = original.get_array_of_samples()
            clipped = sum(abs(v) >= 32700 for v in values) / max(1, len(values)) >= .002
        level = db(clip.rms)
        zcr = audioop.cross(raw, 2) / max(1, len(raw) // 2)
        frames.append({'db': level, 'clipped': clipped, 'zcr': zcr,
                       'tone': tonal_ratio(low[start:start + STEP].raw_data) if level > -50 else 0,
                       'bad': clipped})
    levels = sorted(f['db'] for f in frames)
    if not levels:
        raise ValueError('Recording has no decodable audio.')
    floor, upper = levels[int((len(levels)-1)*.1)], levels[int((len(levels)-1)*.8)]
    warnings = []

    def warn(code, message, recommendation, mask, minimum=1, severity='warning', exclude=False):
        intervals = runs(mask, minimum)
        if not intervals:
            return
        warnings.append({'code': code, 'message': message, 'recommendation': recommendation,
                         'severity': severity, 'intervals': [
                             {'start': a * STEP / 1000, 'end': min(len(recording), b * STEP) / 1000}
                             for a, b in intervals[:8]], 'more_intervals': len(intervals) > 8})
        if exclude:
            for a, b in intervals:
                for f in frames[a:b]:
                    f['bad'] = True

    warn('clipping', 'Repeated near-full-scale samples suggest clipping or saturation.',
         'Lower microphone/input gain. Severe distortion needs a clearer recording; filtering cannot restore lost detail.',
         [f['clipped'] for f in frames], exclude=True)
    warn('long_quiet', 'Long low-level portions contain little usable reference material.',
         'These portions will be avoided where possible. No need to trim the recording manually.',
         [f['db'] < -50 for f in frames], minimum=15, severity='info')
    warn('low_tone', 'A persistent narrow low-frequency tone may be hum or another steady sound.',
         'Listen at the marked times; check the recording environment. The sound source cannot be identified automatically.',
         [f['tone'] > .85 and f['zcr'] < .08 for f in frames], minimum=20, exclude=True)
    warn('high_frequency', 'Persistent high-frequency activity may be hiss or another broadband sound.',
         'Compare the marked audio with a gentle cleanup preview, or record in a quieter environment.',
         [f['zcr'] > .28 and f['db'] > -45 for f in frames], minimum=10, exclude=True)
    spikes = []
    for i, f in enumerate(frames):
        neighbors = [x['db'] for j, x in enumerate(frames[max(0,i-5):i+6], max(0,i-5)) if j != i]
        spikes.append(bool(neighbors) and f['db'] > -12 and f['db'] - statistics.median(neighbors) > 15)
    warn('spikes', 'Abrupt level spikes may be impacts or other short loud sounds.',
         'Listen at the marked times. Reference selection avoids these intervals; the exact cause is unknown.', spikes, exclude=True)
    if -90 < upper < -38:
        warn('quiet_speech', 'Potential speech is extremely quiet; words may be difficult to distinguish.',
             'Move closer to the microphone or rerecord at a healthy input level without clipping.',
             [f['db'] > -90 for f in frames])
    # Level contrast alone cannot distinguish noise from continuous speech/music.
    if floor > -45 and upper - floor < 18:
        warn('background_energy', 'Limited level contrast suggests persistent background energy or continuous sound.',
             'Listen before using this recording. These checks cannot verify intelligibility, music, speaker identity or overlapping voices.',
             [True] * len(frames), minimum=1)
    active_threshold = max(-48, upper - 22)
    for f in frames:
        f['active'] = f['db'] > active_threshold and not f['bad']
    usable = sum(f['active'] for f in frames) * STEP / 1000
    severe = sum(f['clipped'] for f in frames) / len(frames) > .2
    return {'status': 'poor' if severe or usable < 3 else 'review' if warnings else 'good',
            'warnings': warnings, 'potential_speech_seconds': round(usable, 1),
            'resolution_seconds': .1, 'severe_distortion': severe, '_frames': frames}


def select(report, duration, seconds=10):
    """Rank contiguous original windows. Never concatenate syllables or pad silence."""
    frames = report['_frames']
    length = int(seconds * 1000 / STEP)
    if length > len(frames):
        return None
    candidates = []
    for start in range(len(frames) - length + 1):
        end = start + length
        window = frames[start:end]
        if end * STEP > duration * 1000 + 1:
            continue
        active = sum(f['active'] for f in window)
        bad = sum(f['bad'] for f in window)
        quiet_run = max((b-a for a,b in runs([not f['active'] for f in window])), default=0)
        if bad or active / length < .6 or quiet_run * STEP > 1500:
            continue
        # Reward usable coverage, then minimize quiet energy/spikes. A fixed
        # tie preference is only used when quality scores are equal.
        score = active / length - max(0, quiet_run * STEP - 300) / 100000
        preferred = 50 if duration >= 15 else 0
        candidates.append((score, -abs(start-preferred), -start, start))
    if not candidates:
        return None
    start = max(candidates)[-1] * STEP / 1000
    return {'start': start, 'end': start + seconds}


def public(report):
    return {k:v for k,v in report.items() if not k.startswith('_')}


def comparison_regions(report, duration):
    """Offline trial plan only; the runtime default remains a selected 10 s."""
    short = select(report, duration, 10)
    if not short:
        return {'short': [], 'long': []}
    for seconds in (30, 20):
        longer = select(report, duration, seconds)
        if longer:
            return {'short': [short], 'long': [longer]}
    # Fish supports repeated voices fields. Keep separate complete clips rather
    # than stitching disjoint speech into a new, artificial utterance.
    masked = {**report, '_frames': [dict(f) for f in report['_frames']]}
    clips = [short]
    while len(clips) < 3:
        last = clips[-1]
        for frame in masked['_frames'][round(last['start'] * 10):round(last['end'] * 10)]:
            frame['bad'] = True
            frame['active'] = False
        next_clip = select(masked, duration, 10)
        if not next_clip:
            break
        clips.append(next_clip)
    return {'short': [short], 'long': clips if len(clips) >= 2 else []}
