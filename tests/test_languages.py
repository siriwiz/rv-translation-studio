import io
import json
import unittest
from unittest.mock import Mock,patch
from desktop.languages import language_catalog,resolve_language,has_letters,choose_ocr_language,is_rtl,overlay_font
from desktop.translation import Translator,stream_translation,recognize_legacy
from desktop.paragraphs import group_dialogue


class LanguageTests(unittest.TestCase):
    def test_catalog_custom_names_and_unicode(self):
        self.assertGreater(len(language_catalog()),300)
        self.assertEqual(resolve_language('Japanese'),'ja')
        self.assertEqual(resolve_language('ZH-HANT'),'zh-Hant')
        self.assertEqual(resolve_language('en-US'),'en-US')
        self.assertEqual(resolve_language('Klingon'),'custom:Klingon')
        for text in ['猫','สวัสดี','مرحبا','Привет','안녕','Bonjour']:
            self.assertTrue(has_letters(text),text)
        self.assertFalse(has_letters('123 … !'))
        with self.assertRaises(ValueError): resolve_language('')

    def test_ocr_matches_installed_pack_and_never_silently_uses_english(self):
        installed=[('en-US','English'),('ja','Japanese'),('zh-TW','Chinese Traditional'),('fr-FR','French')]
        self.assertEqual(choose_ocr_language('ja',installed),'ja')
        self.assertEqual(choose_ocr_language('fr',installed),'fr-FR')
        self.assertEqual(choose_ocr_language('zh-Hant',installed),'zh-TW')
        with self.assertRaises(RuntimeError): choose_ocr_language('zh-Hans',installed)
        with self.assertRaises(RuntimeError): choose_ocr_language('th',installed)
        self.assertEqual(choose_ocr_language('auto',installed),'en-US')
        self.assertEqual(choose_ocr_language('auto',installed,'ja'),'ja')

    def test_unicode_legacy_filter_and_requested_profile(self):
        entries=[dict(text=t) for t in ['猫','สวัสดี','مرحبا','123']]
        completed=Mock(returncode=0,stdout=json.dumps(entries))
        with patch('desktop.translation.subprocess.run',return_value=completed) as run:
            self.assertEqual([x['text'] for x in recognize_legacy('image.png','ja')],['猫','สวัสดี','مرحبا'])
        self.assertEqual(run.call_args.args[0][-2:],['-LanguageTag','ja'])

    def test_target_and_auto_source_are_in_real_request(self):
        stream=b'data: {"type":"response.output_text.delta","delta":"{\\"translations\\":[\\"ok\\"]}"}\n\ndata: {"type":"response.completed"}\n\n'
        for source,target,name in [('auto','ja','Japanese'),('ja','en','English'),('en','ar','Arabic')]:
            with patch('desktop.translation.urlopen',return_value=io.BytesIO(stream)) as opened:
                self.assertEqual(stream_translation('fake','model',['猫'],source=source,target=target),['ok'])
            payload=json.loads(opened.call_args.args[0].data)
            self.assertIn(name,payload['instructions'])
            if source=='auto': self.assertIn('automatically',payload['instructions'])
            self.assertEqual(json.loads(payload['input'][0]['content']),['猫'])

    @patch('desktop.translation.write_json')
    @patch('desktop.translation.read_json',return_value={})
    def test_cache_separates_source_and_target_languages(self,read,write):
        translator=Translator(); token=Mock(return_value='fake')
        with patch('desktop.translation.stream_translation',side_effect=[['猫'],['แมว'],['different context']]) as stream:
            self.assertEqual(translator.translate(['cat'],token,'model',source='en',target='ja'),(['猫'],0))
            self.assertEqual(translator.translate(['cat'],token,'model',source='en',target='th'),(['แมว'],0))
            self.assertEqual(translator.translate(['cat'],token,'model',source='auto',target='ja'),(['different context'],0))
            self.assertEqual(translator.translate(['cat'],token,'model',source='en',target='ja'),(['猫'],1))
        self.assertEqual(stream.call_count,3)
        self.assertEqual(token.call_count,3)

    def test_same_language_is_preserved_without_api_or_auth(self):
        with patch('desktop.translation.read_json',return_value={}): translator=Translator()
        token=Mock()
        self.assertEqual(translator.translate(['猫'],token,'model',source='ja',target='ja'),(['猫'],0))
        token.assert_not_called()

    def test_script_fonts_and_direction(self):
        self.assertTrue(is_rtl('ar')); self.assertTrue(is_rtl('auto','שלום'))
        self.assertFalse(is_rtl('ja')); self.assertIn('Gothic',overlay_font('ja'))

    def test_cjk_continuation_without_invented_spaces(self):
        def line(text,y): return dict(text=text,x=40,y=y,w=400,h=24)
        joined=group_dialogue([line('あの夜あなたがこの谷に',40),line('戻ったことを覚えている。',72)],language='ja')
        self.assertEqual(len(joined),1)
        self.assertEqual(joined[0]['text'],'あの夜あなたがこの谷に戻ったことを覚えている。')
        self.assertEqual(len(group_dialogue([line('これは終わった文章。',40),line('こちらは別の文章です。',72)],language='ja')),2)
