import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.build-tools'))
import desktop
import cv2,numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase,QImage,QPainter,QColor
from desktop.storage import resource
from desktop.text_layout import translation_layout,paint_translation
from desktop.blend import make_patches,image_to_bgr
from desktop.glyphs import refine_rapid_regions
from desktop.paragraphs import group_dialogue


class OverlayRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication(['RV-render-tests'])
        QFontDatabase.addApplicationFont(str(resource('PlaypenSansThai-Light.ttf')))
        QFontDatabase.addApplicationFont(str(resource('Sarabun-Regular.ttf')))

    def test_scale_changes_actual_font_and_painted_pixels(self):
        item=dict(x=40,y=45,w=300,h=48,line_height=26,translation='หุบเขาแห่งนี้ยังจดจำคุณได้',target_language='th',text_bounds=(0,0,900,300))
        sizes=[];painted=[]
        for scale in (12,20,36):
            layout,origin,ink,size,room=translation_layout(item,scale);sizes.append(size)
            image=QImage(900,300,QImage.Format.Format_RGB32);image.fill(QColor('black'));p=QPainter(image);paint_translation(p,item,scale);p.end()
            frame=image_to_bgr(image);ys,xs=np.nonzero(frame[:,:,0]>100);painted.append((xs.max()-xs.min(),ys.max()-ys.min()))
        self.assertLess(sizes[0],sizes[1]);self.assertGreater(sizes[2],sizes[1]*1.65)
        self.assertGreater(painted[2][0]*painted[2][1],painted[1][0]*painted[1][1]*1.8)

    def test_scaled_text_stays_inside_screen_edges(self):
        item=dict(x=650,y=170,w=200,h=28,translation='This is a long translated sentence that grows.',target_language='en',text_bounds=(0,0,900,240))
        _,_,ink,_,room=translation_layout(item,36)
        self.assertLessEqual(ink.right(),room.right()+1);self.assertLessEqual(ink.bottom(),room.bottom()+1)

    def test_glyph_masks_remove_text_without_erasing_word_gap_texture(self):
        frame=np.full((110,480,3),(32,45,43),np.uint8)
        for x in range(0,480,20):frame[:,x:x+7]=(37,52,49)
        original=frame.copy()
        cv2.putText(frame,'Hi.    valley!',(25,67),cv2.FONT_HERSHEY_SIMPLEX,1,(102,188,231),2,cv2.LINE_AA)
        line=dict(text='Hi. valley!',x=18,y=36,w=300,h=40,words=[dict(x=20,y=36,w=300,h=40)])
        refine_rapid_regions(frame,[line]);self.assertIn('glyph_masks',line)
        patch,rect=make_patches(frame,[line],padding=1)[0]
        cleaned=frame.copy();x,y=int(rect.x()),int(rect.y());crop=image_to_bgr(patch);cleaned[y:y+crop.shape[0],x:x+crop.shape[1]]=crop
        source_ink=frame[:,:,2]>150
        self.assertLess(np.count_nonzero(cleaned[:,:,2]>150),np.count_nonzero(source_ink)*.02)
        self.assertTrue(np.array_equal(cleaned[40:65,80:85],original[40:65,80:85]))

    def test_shared_restore_does_not_reintroduce_neighbor_text(self):
        frame=np.full((90,300,3),25,np.uint8)
        cv2.putText(frame,'First',(20,34),cv2.FONT_HERSHEY_SIMPLEX,.7,(240,240,240),1,cv2.LINE_AA)
        cv2.putText(frame,'Second',(20,62),cv2.FONT_HERSHEY_SIMPLEX,.7,(240,240,240),1,cv2.LINE_AA)
        lines=[dict(text='First',x=18,y=17,w=70,h=20),dict(text='Second',x=18,y=44,w=90,h=20)]
        result=frame.copy()
        for patch,rect in make_patches(frame,lines):
            x,y=int(rect.x()),int(rect.y());crop=image_to_bgr(patch);result[y:y+crop.shape[0],x:x+crop.shape[1]]=crop
        self.assertFalse(np.any(result[17:64,18:110]>100))
