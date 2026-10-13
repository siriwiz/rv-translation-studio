"""Windows OCR on one persistent COM worker; no shell process per capture."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from .languages import has_letters

_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='windows-ocr')
_engines = {}
_initialized = False


def _initialize():
    global _initialized
    from winrt.runtime import init_apartment, ApartmentType
    if not _initialized:
        init_apartment(ApartmentType.MULTI_THREADED)
        _initialized = True


def _languages():
    _initialize()
    from winrt.windows.media.ocr import OcrEngine
    return [(language.language_tag,language.display_name) for language in OcrEngine.available_recognizer_languages]


def installed_languages():
    return _worker.submit(_languages).result(timeout=10)


def _recognize(path,language):
    _initialize()
    from winrt.windows.globalization import Language
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.storage import StorageFile, FileAccessMode
    if language not in _engines:
        engine = OcrEngine.try_create_from_language(Language(language))
        if engine is None:
            raise RuntimeError(f'Windows OCR for {language} is not installed. Open Settings → Windows language packs.')
        _engines[language] = engine
    engine = _engines[language]

    async def read():
        file = await StorageFile.get_file_from_path_async(str(path.resolve()))
        stream = await file.open_async(FileAccessMode.READ)
        try:
            decoder = await BitmapDecoder.create_async(stream)
            bitmap = await decoder.get_software_bitmap_async()
            try:
                result = await engine.recognize_async(bitmap)
                lines = []
                for line in result.lines:
                    words = [dict(text=w.text, x=w.bounding_rect.x, y=w.bounding_rect.y,
                                  w=w.bounding_rect.width, h=w.bounding_rect.height) for w in line.words]
                    if not words or not has_letters(line.text):
                        continue
                    x, y = min(w['x'] for w in words), min(w['y'] for w in words)
                    lines.append(dict(text=line.text, x=x, y=y,
                                      w=max(w['x']+w['w'] for w in words)-x,
                                      h=max(w['y']+w['h'] for w in words)-y, words=words))
                return lines[:100]
            finally:
                bitmap.close()
        finally:
            stream.close()
    return asyncio.run(read())


def recognize_native(path,language='en-US'):
    return _worker.submit(_recognize, path,language).result(timeout=45)
