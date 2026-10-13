import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.build-tools'))
import numpy as np
from desktop.ocr_profiles import resolve_ocr_language, profiles_for
from desktop.rapid_ocr import convert_result, merge_text_regions
from desktop.translation import recognize


class OCREngineTests(unittest.TestCase):
    def test_rapid_routes_without_windows_packs(self):
        for language,profile in [('en','en'),('th','th'),('ja','ch'),('zh-Hant','ch'),('ko','korean'),
                                 ('fr','latin'),('vi','latin'),('ru','cyrillic'),('ar','arabic'),
                                 ('hi','devanagari'),('el','el'),('ta','ta'),('te','te')]:
            self.assertEqual(resolve_ocr_language(language,[],backend='rapid'),'rapid:'+profile)

    def test_profile_override_and_unsupported_language(self):
        self.assertEqual(resolve_ocr_language('auto',[],'rapid:th','rapid'),'rapid:th')
        self.assertEqual(resolve_ocr_language('auto',[],backend='rapid'),'rapid:ch')
        with self.assertRaisesRegex(RuntimeError,'no bundled'):
            resolve_ocr_language('bn',[],backend='rapid')
        with self.assertRaises(RuntimeError):
            resolve_ocr_language('en',[],'en-US','rapid')
        with self.assertRaises(RuntimeError):
            resolve_ocr_language('th',[('en-US','English')],backend='native')

    def test_engine_dispatch_never_silently_changes_engine(self):
        with patch('desktop.rapid_ocr.recognize_rapid',return_value=['rapid']) as rapid:
            self.assertEqual(recognize('image.png','rapid','rapid:th'),['rapid'])
            rapid.assert_called_once_with('image.png','rapid:th')
        with self.assertRaises(ValueError): recognize('image.png','unknown')
        self.assertEqual(len(profiles_for('rapid',[])),11)

    def test_original_image_word_bounds_are_clipped_and_preserved(self):
        quad=np.array([[-5,-2],[80,-2],[80,22],[-5,22]])
        word_quad=np.array([[10,2],[40,2],[40,20],[10,20]])
        result=SimpleNamespace(txts=('Hello',),boxes=(quad,),word_results=((('Hello',.95,word_quad),),))
        line=convert_result(result,100,60)[0]
        self.assertEqual((line['x'],line['y'],line['w'],line['h']),(0.,0.,80.,22.))
        self.assertEqual(line['words'][0]['x'],10.)
        self.assertEqual(line['words'][0]['w'],30.)

    def test_detector_joins_near_fragments_but_keeps_columns_and_rows(self):
        def quad(x,y,w=60,h=20): return [[x,y],[x+w,y],[x+w,y+h],[x,y+h]]
        boxes,scores=merge_text_regions(np.array([quad(10,10),quad(65,11),quad(300,10),quad(10,50)]),[.9,.8,.95,.99])
        self.assertEqual(len(boxes),3)
        self.assertEqual(boxes[0].tolist(),quad(10,10,115,21))
        self.assertAlmostEqual(scores[0],.8)


if __name__=='__main__': unittest.main()
