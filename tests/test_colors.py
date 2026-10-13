import unittest
import cv2
import numpy as np
from desktop.blend import make_patch, image_to_bgr
from desktop.colors import sample_text_color
from desktop.paragraphs import group_dialogue


class ColorTests(unittest.TestCase):
    def sample(self,rgb,background,outline=None):
        frame=np.full((100,500,3),background,dtype=np.uint8)
        # Source text occupies only a minority of its box; averaging would fail.
        if outline is not None:
            cv2.putText(frame,'Valley remembers',(12,62),cv2.FONT_HERSHEY_SIMPLEX,1,outline,5,cv2.LINE_AA)
        cv2.putText(frame,'Valley remembers',(12,62),cv2.FONT_HERSHEY_SIMPLEX,1,tuple(reversed(rgb)),2,cv2.LINE_AA)
        line=dict(text='Valley remembers',x=10,y=36,w=295,h=30)
        patch,rect=make_patch(frame,line)
        return sample_text_color(frame,line,patch,rect)

    def test_anti_aliased_white_and_colored_glyphs(self):
        for rgb in ((245,245,245),(247,191,60),(230,66,74),(55,210,225),(40,40,40)):
            with self.subTest(rgb=rgb):
                style=self.sample(rgb,220 if rgb==(40,40,40) else 28)
                self.assertLess(np.linalg.norm(np.array(style['text_color'])-rgb),15,style)
                self.assertGreater(style['color_confidence'],.15)

    def test_colored_fill_surrounded_by_white_outline(self):
        style=self.sample((230,66,74),28,outline=(245,245,245))
        self.assertLess(np.linalg.norm(np.array(style['text_color'])-[230,66,74]),18,style)

    def test_flat_region_falls_back_without_sampling_background(self):
        frame=np.full((80,200,3),70,dtype=np.uint8)
        line=dict(x=20,y=20,w=100,h=30)
        patch,rect=make_patch(frame,line)
        style=sample_text_color(frame,line,patch,rect)
        self.assertEqual(style['text_color'],(255,255,255))
        self.assertEqual(style['color_confidence'],0)

    def test_different_speaker_colors_remain_separate(self):
        lines=[dict(text='I still remember the night',x=20,y=20,w=350,h=25,
                    text_color=(245,245,245),color_confidence=.9),
               dict(text='you came back to the valley.',x=20,y=52,w=350,h=25,
                    text_color=(240,185,60),color_confidence=.9)]
        self.assertEqual(len(group_dialogue(lines)),2)
        lines[1]['text_color']=(235,235,235)
        output=group_dialogue(lines)
        self.assertEqual(len(output),1)
        self.assertEqual(output[0]['text_color'],(245,245,245))

    def test_renderer_uses_sampled_fill(self):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QImage,QPainter,QFontDatabase
        from desktop.text_layout import paint_translation
        from desktop.storage import resource
        app=QApplication.instance() or QApplication([])
        QFontDatabase.addApplicationFont(str(resource('PlaypenSansThai-Light.ttf')))
        image=QImage(500,80,QImage.Format.Format_RGB32); image.fill(0xff181818)
        painter=QPainter(image)
        paint_translation(painter,dict(x=20,y=20,w=400,h=40,translation='หุบเขาแห่งนี้ยังจดจำคุณได้',
                                      text_color=(247,191,60)),20)
        painter.end()
        pixels=image_to_bgr(image).reshape(-1,3).astype(int)
        distance=np.linalg.norm(pixels-[60,191,247],axis=1)
        self.assertGreater(np.count_nonzero(distance<12),30)


if __name__=='__main__':
    unittest.main()
