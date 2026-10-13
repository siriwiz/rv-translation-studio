"""Fit once at 100%, then honor the user scale in overlay and preview."""
from PyQt6.QtCore import QRectF,QPointF,Qt
from PyQt6.QtGui import QFont,QColor,QTextLayout,QTextOption
from .languages import overlay_font,is_rtl
from functools import lru_cache


@lru_cache(maxsize=256)
def display_text(text,language):
    if language.split('-')[0]=='th':
        from pythainlp.tokenize.newmm import segment
        return '\u200b'.join(segment(text))
    return text


def _layout(text,font,width,rtl):
    layout=QTextLayout(text,font)
    option=QTextOption();option.setWrapMode(QTextOption.WrapMode.WordWrap)
    option.setTextDirection(Qt.LayoutDirection.RightToLeft if rtl else Qt.LayoutDirection.LeftToRight)
    option.setAlignment(Qt.AlignmentFlag.AlignRight if rtl else Qt.AlignmentFlag.AlignLeft)
    layout.setTextOption(option);layout.beginLayout();height=0.
    while True:
        line=layout.createLine()
        if not line.isValid():break
        line.setLineWidth(max(12,width));line.setPosition(QPointF(0,height));height+=line.height()
    layout.endLayout();ink=QRectF()
    for run in layout.glyphRuns():
        raw=run.rawFont()
        for glyph,position in zip(run.glyphIndexes(),run.positions()):
            rect=raw.boundingRect(glyph).translated(position)
            if not rect.isEmpty():ink=ink.united(rect)
    return layout,ink


def translation_layout(item,font_size):
    language=item.get('target_language','th');text=display_text(item['translation'],language);rtl=is_rtl(language,text)
    font=QFont(overlay_font(language));font.setFamilies([overlay_font(language),'Segoe UI','Nirmala UI','Microsoft YaHei','Yu Gothic','Malgun Gothic'])
    width=max(12,item['w']);source_height=max(12,item['h']);base=max(9,round(item.get('line_height',source_height)*.95))
    while True:
        font.setPixelSize(base);layout,ink=_layout(text,font,width,rtl)
        if ink.height()<=source_height+3 or base<=9:break
        base-=1
    scale=max(.3,float(font_size)/20);size=max(7,round(base*scale));font.setPixelSize(size)
    room=QRectF(*item.get('text_bounds',(0,0,max(4096,item['x']+item['w']*3),max(4096,item['y']+item['h']*4))))
    scaled_width=min(max(12,room.right()-item['x']),width*max(1.,scale))
    layout,ink=_layout(text,font,scaled_width,rtl)
    x=item['x']+(item['w']-ink.width() if rtl else 0);y=item['y']
    x=max(room.left(),min(x,room.right()-ink.width()));y=max(room.top(),min(y,room.bottom()-ink.height()))
    origin=QPointF(x-ink.x(),y-ink.y())
    return layout,origin,ink.translated(origin),size,room


def paint_translation(p,item,font_size):
    layout,origin,ink,size,room=translation_layout(item,font_size)
    p.save();p.setClipRect(room,Qt.ClipOperation.IntersectClip)
    p.setPen(QColor(0,0,0,200));layout.draw(p,origin+QPointF(1,1))
    p.setPen(QColor(*item.get('text_color',(255,255,255))));layout.draw(p,origin);p.restore()
    return ink,size
