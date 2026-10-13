"""Offline sentence boundaries for the sentence-trained local translation models."""
from functools import lru_cache
import re
import threading

_lock=threading.RLock()


@lru_cache(maxsize=10)
def _segmenter(language):
    from pysbd import Segmenter
    from pysbd.languages import LANGUAGE_CODES
    return Segmenter(language=language if language in LANGUAGE_CODES else 'en',
                     clean=False,char_span=True)


def split_sentences(text,language):
    # Use original source slices, not transformed segmenter text. This also keeps
    # any gaps/tail that a boundary detector fails to label, with no dropped text.
    cursor=0;parts=[]
    with _lock:spans=_segmenter(language.split('-')[0]).segment(text)
    for span in spans:
        end=span.end
        if cursor<end<=len(text):
            value=text[cursor:end].strip()
            if value:parts.append(value)
            cursor=end
    tail=text[cursor:].strip()
    if tail:parts.append(tail)
    return parts or [text.strip()]


def join_sentences(parts,language):
    return ('' if language.split('-')[0] in ('zh','ja') else ' ').join(parts)


def split_auto_sentences(text):
    # Handle CJK/Latin boundaries and OCR line breaks. Embedded single names,
    # such as OpenAI inside a Japanese sentence, stay with that sentence.
    hint='ja' if re.search(r'[\u3040-\u30ff]',text) else 'zh' if re.search(r'[\u3400-\u9fff]',text) else 'en'
    output=[];cjk=r'[\u3040-\u30ff\u3400-\u9fff]'
    for sentence in split_sentences(text,hint):
        parts=re.split(r'(?<='+cjk+r')\s*(?=[A-Za-z])|(?<=[A-Za-z])\s*(?='+cjk+r')',sentence)
        latin=[part.strip() for part in parts if re.search('[A-Za-z]',part) and not re.search(cjk,part)]
        common={'hello','hi','yes','no','ok','okay','continue','cancel','back','exit','settings','start','resume'}
        bilingual=len(parts)>1 and latin and all(len(re.findall('[A-Za-z]+',part))>=2 or part.strip(' .!?').casefold() in common for part in latin)
        output.extend(part.strip() for part in (parts if bilingual else [sentence]) if part.strip())
    return output
