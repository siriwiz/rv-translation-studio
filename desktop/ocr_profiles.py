"""Engine capabilities and routing, without loading inference libraries in the UI."""
from .languages import choose_ocr_language, language_name
from .storage import resource

PROFILES = {
    'en': 'English',
    'ch': 'Chinese / Japanese / English',
    'korean': 'Korean / English',
    'latin': 'Latin scripts / Vietnamese',
    'th': 'Thai / English',
    'cyrillic': 'Cyrillic scripts / Russian',
    'arabic': 'Arabic scripts / Persian / Urdu',
    'devanagari': 'Devanagari / Hindi / Nepali',
    'el': 'Greek / English',
    'ta': 'Tamil / English',
    'te': 'Telugu / English',
}
LANGUAGE_GROUPS = {
    'en': 'en', 'zh': 'ch', 'ja': 'ch', 'ko': 'korean', 'th': 'th',
    'el': 'el', 'ta': 'ta', 'te': 'te',
}
for _group, _codes in {
    'latin': 'af az bs ca cs cy da de es et eu fi fr ga gl hr hu id is it la lb lt lv mi ms mt nb nn no oc pl pt qu rm ro sk sl sq sv sw tl fil tr uz vi',
    'cyrillic': 'ru be uk sr bg mn ab ady kbd av dar inh ce lbe lez tab kk ky tg mk tt cv ba udm kv os bua xal tyv sah kaa',
    'arabic': 'ar fa ug ur ps sd bal',
    'devanagari': 'hi mr ne bh mai anp bho mag new kok sa bgc',
}.items():
    LANGUAGE_GROUPS.update(dict.fromkeys(_codes.split(), _group))


def profiles_for(backend, installed):
    if backend == 'rapid':
        return [(f'rapid:{key}', name) for key, name in PROFILES.items()]
    return installed


def model_paths(profile):
    if profile not in PROFILES:
        raise RuntimeError('Choose a supported RapidOCR reading profile in Settings.')
    paths = (resource('assets/ocr/ch_PP-OCRv5_det_mobile.onnx'),
             resource(f'assets/ocr/{profile}_PP-OCRv5_rec_mobile.onnx'))
    if not all(path.is_file() for path in paths):
        raise RuntimeError('Bundled RapidOCR models are missing. Reinstall the full RV TRANSLATION STUDIO build.')
    return paths


def resolve_ocr_language(source, installed, override='auto', backend='native'):
    if backend != 'rapid':
        return choose_ocr_language(source, installed, override)
    if override != 'auto':
        profile = override.removeprefix('rapid:') if override.startswith('rapid:') else None
    elif source == 'auto':
        profile = 'ch'  # Covers English, Chinese and Japanese; other scripts need an explicit profile.
    elif source.startswith('sr-Latn'):
        profile = 'latin'
    elif source.startswith('ku-Arab'):
        profile = 'arabic'
    elif source.split('-')[0] == 'ku':
        profile = 'latin'
    else:
        profile = LANGUAGE_GROUPS.get(source.split('-')[0])
    if profile not in PROFILES:
        raise RuntimeError(f'{language_name(source)} has no bundled RapidOCR model. Choose a supported reading profile in Settings, or use Windows OCR if available.')
    model_paths(profile)
    return f'rapid:{profile}'
