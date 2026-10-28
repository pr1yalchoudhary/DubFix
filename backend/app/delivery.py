"""Compose Drama 3 scripts; no transcription or translation is performed."""
import re

LANGUAGES = {'en', 'hi', 'es', 'fr'}
TAGS = {'whisper', 'emphasis', 'soft', 'fast', 'slow', 'stress', 'forceful'}
MARKUP_ERROR = 'Please check the delivery tags in your text.'


def direction_text(value):
    value = ' '.join((value or '').split())
    # Accept a plain direction or an already bracketed one without doubling it.
    while value.startswith('[') and value.endswith(']'):
        value = value[1:-1].strip()
    if any(c in value for c in '[]<>'):
        raise ValueError('Enter one performance direction, using plain text or a single pair of square brackets.')
    return value


def validate_script(text):
    stack = []
    # Reject unknown tags, attributes, crossed tags and lone angle brackets.
    for token in re.finditer(r'<[^>]*>|[<>]', text):
        match = re.fullmatch(r'<(/?)([a-z]+)>', token.group())
        if not match or match[2] not in TAGS:
            raise ValueError(MARKUP_ERROR)
        closing, tag = match.groups()
        if closing:
            if not stack or stack.pop() != tag:
                raise ValueError(MARKUP_ERROR)
        else:
            stack.append(tag)
    if stack:
        raise ValueError(MARKUP_ERROR)
    in_cue = False
    for char in text:
        if char == '[':
            if in_cue:
                raise ValueError(MARKUP_ERROR)
            in_cue = True
        elif char == ']':
            if not in_cue:
                raise ValueError(MARKUP_ERROR)
            in_cue = False
    if in_cue or re.search(r'\[\s*\]', text):
        raise ValueError(MARKUP_ERROR)
    spoken = re.sub(r'\[[^\]]*\]|<[^>]*>', '', text)
    if not any(char.isalnum() for char in spoken):
        raise ValueError('Enter the words you want to regenerate.')


def compose(segment_text, direction=None, language=None, translated_text=None):
    if language not in (None, '', 'original', *LANGUAGES):
        raise ValueError('Choose a supported language from the list.')
    translated = (translated_text or '').strip()
    if language in LANGUAGES and not translated:
        raise ValueError('Enter the text in your selected language.')
    script = translated or (segment_text or '').strip()
    if not script:
        raise ValueError('Enter the words you want to regenerate.')
    validate_script(script)
    direction = direction_text(direction)
    cue = f'[{direction}]' if direction else ''
    # Preserve an already-present identical leading direction exactly once.
    if cue and not script.startswith(cue):
        script = cue + '\n' + script
    if len(script) > 1500:
        raise ValueError('Keep the performance script under 1,500 characters including directions and tags.')
    return script, direction
