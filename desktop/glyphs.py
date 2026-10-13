"""Refine approximate neural OCR boxes into visible glyph masks."""
import cv2
import numpy as np
from .blend import make_patch
from .colors import sample_text_color


def refine_rapid_regions(frame, lines):
    height,width=frame.shape[:2]
    for line in lines:
        rough,rect=make_patch(frame,line,padding=2)
        style=sample_text_color(frame,line,rough,rect)
        x=max(0,int(line['x'])-4);y=max(0,int(line['y'])-4)
        right=min(width,int(np.ceil(line['x']+line['w']))+4)
        bottom=min(height,int(np.ceil(line['y']+line['h']))+4)
        roi=frame[y:bottom,x:right]
        if not roi.size: continue
        kernel=max(5,min(31,int(line['h']*.65)|1))
        background=cv2.medianBlur(roi,kernel)
        lab=cv2.cvtColor(roi,cv2.COLOR_BGR2LAB).astype(np.float32)
        bg=cv2.cvtColor(background,cv2.COLOR_BGR2LAB).astype(np.float32)
        contrast=np.linalg.norm(lab-bg,axis=2)
        if style['color_confidence']>=.15:
            color=np.array(style['text_color'][::-1],dtype=np.float32)
            color_distance=np.linalg.norm(roi.astype(np.float32)-color,axis=2)
            candidate=((color_distance<60)&(contrast>10)).astype(np.uint8)
        else:candidate=(contrast>28).astype(np.uint8)
        count,labels,stats,_=cv2.connectedComponentsWithStats(candidate,8)
        mask=np.zeros(candidate.shape,dtype=np.uint8)
        h=line['h']
        for index in range(1,count):
            left,top,w,component_h,area=stats[index]
            if area<1 or component_h>h*1.35: continue
            if style['color_confidence']<.15 and (area<3 or component_h<max(2,h*.08)):continue
            if w>max(h*6,line['w']*.85) and component_h<h*.2: continue
            if left==0 or top==0 or left+w==roi.shape[1] or top+component_h==roi.shape[0]: continue
            mask[labels==index]=255
        if np.count_nonzero(mask)<8: continue
        mask=cv2.dilate(mask,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
        ys,xs=np.nonzero(mask)
        left,top,right,bottom=int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)
        line.update(x=float(x+left),y=float(y+top),w=float(right-left),h=float(bottom-top),
                    glyph_masks=[(x+left,y+top,mask[top:bottom,left:right].copy())],**style)
    return lines
