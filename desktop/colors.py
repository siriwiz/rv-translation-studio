"""Estimate glyph fill from OCR word pixels, excluding the reconstructed background."""
import cv2
import numpy as np
from .blend import image_to_bgr


def sample_text_color(frame, line, cleaned_patch, patch_rect):
    x, y = int(patch_rect.x()), int(patch_rect.y())
    clean = image_to_bgr(cleaned_patch)
    source = frame[y:y+clean.shape[0], x:x+clean.shape[1]]
    mask = np.zeros(clean.shape[:2], dtype=np.uint8)
    words = line.get('words') or [line]
    if isinstance(words, dict):
        words = [words]
    for word in words:
        if not isinstance(word, dict) or not all(k in word for k in ('x', 'y', 'w', 'h')):
            continue
        left, top = max(0, int(word['x'])-x), max(0, int(word['y'])-y)
        right = min(mask.shape[1], int(np.ceil(word['x']+word['w']))-x)
        bottom = min(mask.shape[0], int(np.ceil(word['y']+word['h']))-y)
        mask[top:bottom, left:right] = 1
    lab = cv2.cvtColor(source, cv2.COLOR_BGR2LAB).astype(np.float32)
    background = cv2.cvtColor(clean, cv2.COLOR_BGR2LAB).astype(np.float32)
    contrast = np.linalg.norm(lab-background, axis=2)
    candidates = (mask > 0) & (contrast >= 18)
    if np.count_nonzero(candidates) < 8:
        return {'text_color': (255, 255, 255), 'color_confidence': 0.}
    pixels = source[candidates]
    weights = contrast[candidates]
    # Quantize for voting, then recover actual RGB from the winning glyph cores.
    bins = pixels.astype(np.int32)//24
    keys = bins[:, 0]*121 + bins[:, 1]*11 + bins[:, 2]
    votes = np.bincount(keys, weights=weights)
    winner = int(np.argmax(votes))
    chosen = keys == winner
    # A colored fill can be surrounded by a high-contrast white/black outline.
    # Prefer a substantial chromatic cluster to that neutral outline.
    chroma = pixels.max(axis=1).astype(float)-pixels.min(axis=1)
    colorful = chroma > 45
    if colorful.any():
        color_votes = np.bincount(keys[colorful], weights=weights[colorful], minlength=len(votes))
        color_winner = int(np.argmax(color_votes))
        if color_votes[color_winner] >= votes[winner]*.45:
            winner = color_winner
            chosen = keys == winner
    # Include adjacent quantization bins of the same fill; avoid a bin-edge bias.
    center = np.median(pixels[chosen], axis=0)
    near = np.linalg.norm(pixels.astype(float)-center, axis=1) < 25
    core = near & (weights >= np.percentile(weights[near], 35))
    bgr = np.median(pixels[core], axis=0).round().astype(int)
    confidence = min(1., float(votes[winner]/max(1., votes.sum()))*2)
    return {'text_color': tuple(int(c) for c in bgr[::-1]), 'color_confidence': confidence}


def compatible_colors(a, b):
    if min(a.get('color_confidence', 0), b.get('color_confidence', 0)) < .15:
        return True
    ca, cb = a.get('text_color'), b.get('text_color')
    return ca is None or cb is None or sum((x-y)**2 for x,y in zip(ca,cb)) <= 70**2
