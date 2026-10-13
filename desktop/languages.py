"""Searchable locale catalog, Unicode text handling, and explicit OCR routing."""
import unicodedata
import re
from functools import lru_cache
from PyQt6.QtCore import QLocale, Qt


@lru_cache(maxsize=1)
def language_catalog():
    result = {}
    for language in QLocale.Language:
        code = QLocale.languageToCode(language)
        if code and code != 'C':
            result[code] = QLocale.languageToString(language)
    result.pop('zh',None)
    result.update({'zh-Hans':'Chinese (Simplified)','zh-Hant':'Chinese (Traditional)',
                   'pt-BR':'Portuguese (Brazil)','pt-PT':'Portuguese (Portugal)'})
    return sorted(result.items(),key=lambda item:item[1].casefold())


def language_name(code):
    if code == 'auto': return 'Auto detect'
    if code.startswith('custom:'): return code[7:]
    return dict(language_catalog()).get(code,QLocale(code).nativeLanguageName() or code)


def language_badge(code):
    if code == 'auto': return 'AUTO'
    if code.startswith('custom:'): return code[7:15].upper()
    return code.upper()


def resolve_language(value):
    value = value.strip()
    for code,name in language_catalog():
        if value.casefold() in (code.casefold(),name.casefold()):
            return code
    if value.casefold() in ('auto','auto detect'): return 'auto'
    if re.fullmatch(r'[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})+',value) and QLocale(value).language()!=QLocale.Language.C:
        return value
    if not value or len(value)>80 or any(unicodedata.category(c).startswith('C') for c in value):
        raise ValueError('Enter a language name of up to 80 characters.')
    return 'custom:'+value


def has_letters(text):
    return any(char.isalpha() for char in text.strip())


def is_rtl(code,text=''):
    if code not in ('auto','') and not code.startswith('custom:'):
        return QLocale(code).textDirection() == Qt.LayoutDirection.RightToLeft
    for char in text:
        direction=unicodedata.bidirectional(char)
        if direction in ('R','AL'): return True
        if direction == 'L': return False
    return False


def overlay_font(code):
    primary = code.split('-')[0]
    return {'en':'Playpen Sans Thai','th':'Playpen Sans Thai','ja':'Yu Gothic','ko':'Malgun Gothic',
            'zh':'Microsoft JhengHei' if 'Hant' in code else 'Microsoft YaHei',
            'hi':'Nirmala UI','bn':'Nirmala UI','ta':'Nirmala UI','te':'Nirmala UI'}.get(primary,'Segoe UI')


def choose_ocr_language(source,installed,override='auto'):
    tags = [item[0] for item in installed]
    if override != 'auto':
        if override in tags: return override
        raise RuntimeError('The selected OCR language is no longer installed. Reload OCR languages in Settings.')
    if source == 'auto':
        if 'en-US' in tags: return 'en-US'
        if tags: return tags[0]
    if source in tags: return source
    prefix=source.split('-')[0]
    candidates=[tag for tag in tags if tag.split('-')[0]==prefix]
    if prefix=='zh':
        preferred=('zh-TW','zh-HK','zh-Hant') if 'Hant' in source else ('zh-CN','zh-Hans')
        candidates=[tag for tag in candidates if tag in preferred or any(part in tag for part in preferred)]
    if candidates: return candidates[0]
    raise RuntimeError(f'{language_name(source)} OCR is not installed or supported by Windows on this PC. Install a matching Windows OCR pack, or choose an installed OCR profile in Settings. Text samples can still be translated.')
