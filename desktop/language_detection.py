"""Bundled text-language identification; never downloads models or uses a service."""
import unicodedata
from functools import cached_property, lru_cache


class LocalLanguageDetector:
    @cached_property
    def detectors(self):
        from lingua import Language, LanguageDetectorBuilder
        languages=(Language.ENGLISH,Language.THAI,Language.CHINESE,Language.JAPANESE,
                   Language.KOREAN,Language.FRENCH,Language.GERMAN,Language.SPANISH,
                   Language.VIETNAMESE,Language.RUSSIAN)
        # Accurate short dialogue detection for the bundled languages. A broad,
        # lightweight guard avoids forcing clear unsupported text into this set.
        return (LanguageDetectorBuilder.from_languages(*languages).build(),
                LanguageDetectorBuilder.from_all_languages().with_low_accuracy_mode().build())

    @lru_cache(maxsize=512)
    def detect(self,text):
        text=unicodedata.normalize('NFKC',text).strip()
        if not any(char.isalpha() for char in text):return None
        word=text.casefold().strip(' .!?…,:;\"\'')
        # Common standalone game controls/greetings have too little statistical
        # evidence. Resolve these deterministically, independently of batch/cache.
        if word in {'hello','hi','yes','no','ok','okay','continue','cancel','back','exit',
                    'settings','loading','start','resume','save','load','quit','confirm','accept','retry'}:return 'en'
        if word in {'bonjour','merci','bonsoir','salut'}:return 'fr'
        if word in {'hola','gracias'}:return 'es'
        if word in {'hallo','danke'}:return 'de'
        detector,guard=self.detectors
        broad=guard.compute_language_confidence_values(text)
        ranked=detector.compute_language_confidence_values(text)
        supported={value.language for value in ranked}
        if broad and broad[0].value>=.7 and broad[0].language not in supported:
            name=broad[0].language.name.replace('_',' ').title()
            raise RuntimeError('Auto detect identified '+name+', which is not bundled in Argos Local. Choose a cloud provider for this language.')
        if not ranked or ranked[0].value<.45:
            raise RuntimeError('Auto detect could not identify this short or ambiguous passage. Choose its source language in Studio and retry.')
        return ranked[0].language.iso_code_639_1.name.lower()
