"""Offline CPU OCR with bundled PP-OCRv5 models and bounded session reuse."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import numpy as np
from .languages import has_letters
from .ocr_profiles import model_paths
from .storage import resource

_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='rapid-ocr')
_engines = OrderedDict()
_detector = None


def merge_text_regions(boxes, scores):
    """Read nearby horizontal fragments together, avoiding clipped/doubled words."""
    if boxes is None or not len(boxes):
        return boxes, scores
    rows = []
    for index in np.argsort(np.asarray(boxes)[:, :, 1].mean(axis=1), kind='stable'):
        quad = np.asarray(boxes[index], dtype=np.float32)
        x1, y1 = quad.min(axis=0); x2, y2 = quad.max(axis=0)
        h = y2-y1
        horizontal = abs(quad[1,1]-quad[0,1]) <= max(3, h*.3) and x2-x1 > h*.7
        region = [float(x1),float(y1),float(x2),float(y2),quad,float(scores[index]) if scores is not None else 0.,horizontal]
        row = next((row for row in rows if horizontal and row[0][6]
                    and abs((row[0][1]+row[0][3]-y1-y2)/2) < min(row[0][3]-row[0][1],h)*.35), None)
        if row is None: rows.append([region])
        else: row.append(region)
    merged = []
    for row in rows:
        current = None
        for item in sorted(row,key=lambda r:r[0]):
            h = min(item[3]-item[1],current[3]-current[1]) if current else 0
            gap = item[0]-current[2] if current else 0
            if current and item[6] and current[6] and -h*.6 <= gap <= h*.9:
                current[:4] = [min(current[0],item[0]),min(current[1],item[1]),max(current[2],item[2]),max(current[3],item[3])]
                left,top,right,bottom=current[:4]
                current[4]=np.array([[left,top],[right,top],[right,bottom],[left,bottom]],dtype=np.float32)
                current[5]=min(current[5],item[5])
            else:
                if current: merged.append(current)
                current=item
        if current: merged.append(current)
    merged.sort(key=lambda item:(item[1],item[0]))
    return np.asarray([r[4] for r in merged]), np.asarray([r[5] for r in merged])


class DialogueDetector:
    def __init__(self, detector):
        self.detector=detector

    def __call__(self, image):
        result=self.detector(image)
        result.boxes,result.scores=merge_text_regions(result.boxes,result.scores)
        return result


def _offline_download(*args, **kwargs):
    raise RuntimeError('A bundled OCR resource is missing. Reinstall the full application; runtime model downloads are disabled.')


def _engine(profile):
    global _detector
    if profile in _engines:
        _engines.move_to_end(profile)
        return _engines[profile]
    detector, recognizer = model_paths(profile)
    from rapidocr.main import RapidOCR  # Explicit import also makes PyInstaller discover the implementation.
    from rapidocr import ModelType, OCRVersion
    from rapidocr.utils.download_file import DownloadFile
    DownloadFile.run = staticmethod(_offline_download)
    engine = RapidOCR(params={
        'Global.log_level': 'error', 'Global.use_cls': False,
        'Global.font_path': str(resource('Sarabun-Regular.ttf')),
        'Global.return_word_box': True,
        'EngineConfig.onnxruntime.intra_op_num_threads': max(1, min(4, os.cpu_count() or 1)),
        'EngineConfig.onnxruntime.inter_op_num_threads': 1,
        'Det.ocr_version': OCRVersion.PPOCRV5, 'Det.model_type': ModelType.MOBILE,
        'Det.model_path': str(detector), 'Det.limit_side_len': 960, 'Det.limit_type': 'max',
        'Det.mean': [0.485,0.456,0.406], 'Det.std': [0.229,0.224,0.225],
        'Det.use_dilation': False,
        'Rec.ocr_version': OCRVersion.PPOCRV5, 'Rec.model_type': ModelType.MOBILE,
        'Rec.lang_type': profile, 'Rec.model_path': str(recognizer),
    })
    if _detector is None:
        _detector=DialogueDetector(engine._load_det_model())
    engine.text_det = _detector
    _engines[profile] = engine
    while len(_engines) > 2:
        _engines.popitem(last=False)
    return engine


def _bounds(quad, width, height):
    points = np.asarray(quad, dtype=float)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        return None
    x1, y1 = np.maximum(points.min(axis=0), (0, 0))
    x2, y2 = np.minimum(points.max(axis=0), (width, height))
    if x2 <= x1 or y2 <= y1:
        return None
    return dict(x=float(x1), y=float(y1), w=float(x2-x1), h=float(y2-y1))


def convert_result(result, width, height):
    """Keep original-image word coordinates for color sampling and background blend."""
    if result.txts is None or result.boxes is None:
        return []
    lines = []
    for index, (text, quad) in enumerate(zip(result.txts, result.boxes)):
        box = _bounds(quad, width, height)
        if not box or not has_letters(text):
            continue
        words = []
        if result.word_results and index < len(result.word_results):
            for word in result.word_results[index] or ():
                if not isinstance(word, (tuple, list)) or len(word) != 3 or word[2] is None:
                    continue
                bounds = _bounds(word[2], width, height)
                if bounds:
                    words.append(dict(text=word[0], **bounds))
        # Include word bounds if the detector's line quad is slightly tighter.
        if words:
            left = min(box['x'], *(w['x'] for w in words))
            top = min(box['y'], *(w['y'] for w in words))
            right = max(box['x']+box['w'], *(w['x']+w['w'] for w in words))
            bottom = max(box['y']+box['h'], *(w['y']+w['h'] for w in words))
            box = dict(x=left, y=top, w=right-left, h=bottom-top)
        lines.append(dict(text=text, **box, words=words or [dict(text=text, **box)]))
    return lines[:100]


def _recognize(path, language):
    global _detector
    import cv2
    profile = language.removeprefix('rapid:')
    engine = _engine(profile)
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError('Unable to read the captured image for RapidOCR.')
    result = engine(image)
    _detector = engine.text_det
    return convert_result(result, image.shape[1], image.shape[0])


def recognize_rapid(path, language='rapid:en'):
    return _worker.submit(_recognize, Path(path), language).result(timeout=90)
