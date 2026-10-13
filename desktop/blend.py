"""Restore the original TELEA inpainting overlay from main.legacy.py."""
import cv2
import numpy as np
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QImage


def image_to_bgr(image):
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    data = image.bits()
    data.setsize(image.sizeInBytes())
    pixels = np.frombuffer(data, dtype=np.uint8).reshape(image.height(), image.bytesPerLine())
    rgba = pixels[:, :image.width()*4].reshape(image.height(), image.width(), 4)
    return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)


def make_patch(frame, line, radius=3, padding=1):
    """Mask individual recognized words, retaining background between words."""
    height, width = frame.shape[:2]
    x1 = max(0, int(line['x']) - 10)
    y1 = max(0, int(line['y']) - 10)
    x2 = min(width, int(np.ceil(line['x'] + line['w'])) + 10)
    y2 = min(height, int(np.ceil(line['y'] + line['h'])) + 10)
    if x2 <= x1 or y2 <= y1:
        raise ValueError('Invalid OCR bounds')
    patch = frame[y1:y2, x1:x2].copy()
    mask = np.zeros(patch.shape[:2], dtype=np.uint8)
    words = line.get('words') or [line]
    if isinstance(words, dict):
        words = [words]
    words = [word for word in words if isinstance(word, dict) and all(k in word for k in ('x', 'y', 'w', 'h'))] or [line]
    for word in ([] if line.get('glyph_masks') else words):
        left = max(0, int(word['x']) - x1 - padding)
        top = max(0, int(word['y']) - y1 - padding)
        right = min(x2-x1-1, int(np.ceil(word['x'] + word['w'])) - x1 + padding)
        bottom = min(y2-y1-1, int(np.ceil(word['y'] + word['h'])) - y1 + padding)
        cv2.rectangle(mask, (left, top), (right, bottom), 255, -1)
    for mx,my,glyph_mask in line.get('glyph_masks',[]):
        left,top=max(x1,mx),max(y1,my)
        right,bottom=min(x2,mx+glyph_mask.shape[1]),min(y2,my+glyph_mask.shape[0])
        if right>left and bottom>top:
            mask[top-y1:bottom-y1,left-x1:right-x1] |= glyph_mask[top-my:bottom-my,left-mx:right-mx]
    if line.get('glyph_masks') and padding:
        mask=cv2.dilate(mask,np.ones((2*padding+1,2*padding+1),dtype=np.uint8))
    cleaned = cv2.inpaint(patch, mask, radius, cv2.INPAINT_TELEA)
    ph, pw = cleaned.shape[:2]
    image = QImage(cleaned.data, pw, ph, cleaned.strides[0], QImage.Format.Format_BGR888).copy()
    return image, QRectF(x1, y1, pw, ph)


def make_patches(frame,lines,radius=3,padding=1):
    """One shared restoration prevents overlapping patches restoring old text."""
    height,width=frame.shape[:2];mask=np.zeros((height,width),dtype=np.uint8);bounds=[]
    for line in lines:
        x1=max(0,int(line['x'])-10);y1=max(0,int(line['y'])-10)
        x2=min(width,int(np.ceil(line['x']+line['w']))+10);y2=min(height,int(np.ceil(line['y']+line['h']))+10)
        bounds.append((x1,y1,x2,y2))
        if line.get('glyph_masks'):
            for x,y,glyph in line['glyph_masks']:
                right,bottom=min(width,x+glyph.shape[1]),min(height,y+glyph.shape[0]);left,top=max(0,x),max(0,y)
                if right>left and bottom>top:mask[top:bottom,left:right] |= glyph[top-y:bottom-y,left-x:right-x]
        else:
            for word in line.get('words') or [line]:
                left,top=max(0,int(word['x'])),max(0,int(word['y']))
                right,bottom=min(width-1,int(np.ceil(word['x']+word['w']))),min(height-1,int(np.ceil(word['y']+word['h'])))
                cv2.rectangle(mask,(left,top),(right,bottom),255,-1)
    if padding:mask=cv2.dilate(mask,np.ones((2*padding+1,2*padding+1),dtype=np.uint8))
    cleaned=frame.copy()
    if bounds:
        left=min(b[0] for b in bounds);top=min(b[1] for b in bounds);right=max(b[2] for b in bounds);bottom=max(b[3] for b in bounds)
        cleaned[top:bottom,left:right]=cv2.inpaint(frame[top:bottom,left:right],mask[top:bottom,left:right],radius,cv2.INPAINT_TELEA)
    result=[]
    for left,top,right,bottom in bounds:
        patch=cleaned[top:bottom,left:right].copy()
        result.append((QImage(patch.data,right-left,bottom-top,patch.strides[0],QImage.Format.Format_BGR888).copy(),QRectF(left,top,right-left,bottom-top)))
    return result
