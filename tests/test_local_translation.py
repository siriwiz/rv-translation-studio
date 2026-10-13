import sys,unittest,tempfile,os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.build-tools'))
from desktop.local_translation import LocalTranslator
from desktop.translation import Translator
from desktop.sentence_boundaries import split_sentences,split_auto_sentences


class LocalTranslationTests(unittest.TestCase):
    def test_sentence_boundaries_preserve_every_source_character(self):
        samples=[('en',"You hungry?What can we get you? We've got cake. or pizza. Which will it be?"),
                 ('en','Dr. Smith paid $3.14. Wait... Really?'),('zh','你好。你饿了吗？我要蛋糕！'),
                 ('ja','こんにちは。お腹が空いた？ケーキはいかが？'),('ko','안녕하세요. 배고파요? 케이크를 원해요.'),
                 ('th','หิวไหม? คุณอยากกินอะไร? มีเค้กนะ'),('vi','Tôi đói. Bạn có bánh không?'),
                 ('en','First sentence.\nSecond sentence!\nLast tail 😀')]
        for language,text in samples:
            with self.subTest(language=language):
                parts=split_sentences(text,language)
                self.assertGreater(len(parts),1)
                self.assertEqual(''.join(''.join(parts).split()),''.join(text.split()))
        self.assertEqual(split_sentences('Dr. Smith paid $3.14. Next sentence.','en'),['Dr. Smith paid $3.14.','Next sentence.'])

    def test_sentence_batch_reassembles_each_original_passage_in_order(self):
        local=LocalTranslator();batches=[]
        tokenizer=SimpleNamespace(encode=lambda text:[text],decode=lambda pieces:pieces[0])
        def infer(encoded,**options):
            batches.append(encoded)
            return [SimpleNamespace(hypotheses=[[text[0]]]) for text in encoded]
        runtime=SimpleNamespace(translate_batch=infer)
        texts=['First sentence. Second sentence? Last sentence!','Another passage. Its final sentence.']
        with patch.object(local,'_session',return_value=(runtime,tokenizer,'')):
            self.assertEqual(local.complete(None,'argos-quality-v1',texts,source='en',target='th'),texts)
        self.assertEqual(len(batches[0]),5)

    def test_missing_sentence_output_fails_before_caching(self):
        local=LocalTranslator();tokenizer=SimpleNamespace(encode=lambda text:[text],decode=lambda pieces:pieces[0])
        runtime=SimpleNamespace(translate_batch=lambda inputs,**k:[SimpleNamespace(hypotheses=[['Only first sentence.']])] if len(inputs)>1 else [])
        with tempfile.TemporaryDirectory(dir='.') as tmp,patch.dict(os.environ,RUEVALLEY_DATA_DIR=tmp),patch.object(local,'_session',return_value=(runtime,tokenizer,'')):
            translator=Translator()
            with self.assertRaisesRegex(RuntimeError,'incomplete text'):
                translator.translate(['First sentence. Second sentence?'],None,'argos-quality-v1',provider='argos',complete=local.complete)
            self.assertEqual(translator.cache,{})

    def test_symbols_and_numbers_are_preserved_without_inference(self):
        local=LocalTranslator()
        with patch.object(local,'_session',return_value=(SimpleNamespace(translate_batch=lambda *a,**k:self.fail('Symbols reached model')),SimpleNamespace(),'')):
            self.assertEqual(local.complete(None,'argos-quality-v1',['_','123…','00:30'],source='en',target='th'),['_','123…','00:30'])

    def test_empty_sentence_retry_is_isolated_and_successful(self):
        local=LocalTranslator();calls=[]
        tokenizer=SimpleNamespace(encode=lambda text:[text],decode=lambda pieces:pieces[0] if pieces else '')
        def infer(inputs,**options):
            calls.append((inputs,options['beam_size']))
            return [SimpleNamespace(hypotheses=[[] if len(inputs)>1 and tokens[0]=='Retry.' else [tokens[0]]]) for tokens in inputs]
        with patch.object(local,'_session',return_value=(SimpleNamespace(translate_batch=infer),tokenizer,'')):
            self.assertEqual(local.complete(None,'argos-quality-v1',['Good. Retry. Last.'],source='en',target='th'),['Good. Retry. Last.'])
        self.assertEqual(calls[1],([['Retry.']],2));self.assertEqual(len(calls),2)

    def test_screen_failures_are_not_cached_and_other_passages_complete(self):
        local=LocalTranslator();tokenizer=SimpleNamespace(encode=lambda text:[text],decode=lambda pieces:pieces[0] if pieces else '')
        def infer(inputs,**options):return [SimpleNamespace(hypotheses=[[] if 'Bad' in tokens[0] else [tokens[0]+' translated']]) for tokens in inputs]
        with tempfile.TemporaryDirectory(dir='.') as tmp,patch.dict(os.environ,RUEVALLEY_DATA_DIR=tmp),patch.object(local,'_session',return_value=(SimpleNamespace(translate_batch=infer),tokenizer,'')):
            translator=Translator();texts=['Good.','Bad.','Last.']
            values,hits=translator.translate(texts,None,'argos-fast-v1',provider='argos',complete=local.complete_screen,allow_partial=True)
            self.assertEqual(values,['Good. translated',None,'Last. translated'])
            self.assertEqual(len(translator.cache),2)
            values,hits=translator.translate(texts,None,'argos-fast-v1',provider='argos',complete=local.complete_screen,allow_partial=True)
            self.assertEqual(hits,2);self.assertIsNone(values[1])

    def test_auto_routes_japanese_and_english_inside_one_passage(self):
        local=LocalTranslator();seen=[]
        def translate(model,values,route,deadline):
            seen.append((route[0]['source'],values));return [route[0]['source']+':'+value for value in values]
        texts=['こんにちは。Hello, welcome back.','Welcome back.\nこんにちは。','こんにちは Hello, welcome back.']
        with patch.object(local,'_translate',side_effect=translate):
            values=local.complete(None,'argos-fast-v1',texts,source='auto',target='th')
        self.assertEqual([value.split(':')[0] for value in values],['ja','en','ja'])
        self.assertEqual([code for code,_ in seen],['ja','en'])
        self.assertTrue(all('ja:' in value and 'en:' in value for value in values))
        self.assertEqual(split_auto_sentences('彼はOpenAIで働いています。Welcome back, John.'),['彼はOpenAIで働いています。','Welcome back, John.'])

    def test_screen_unknown_source_is_kept_original_without_stopping_valid_text(self):
        local=LocalTranslator()
        with patch.object(local,'_translate',return_value=['Valid translation']):
            self.assertEqual(local.complete_screen(None,'argos-fast-v1',['Hello','X'],source='auto',target='th'),['Valid translation',None])

    def test_english_and_thai_overlay_share_original_font(self):
        from desktop.languages import overlay_font
        self.assertEqual(overlay_font('en'),'Playpen Sans Thai')
        self.assertEqual(overlay_font('en'),overlay_font('th'))

    def test_old_argos_paragraph_cache_is_not_reused(self):
        text='First question? Second question?'
        with tempfile.TemporaryDirectory(dir='.') as tmp,patch.dict(os.environ,RUEVALLEY_DATA_DIR=tmp):
            translator=Translator()
            old='argos|argos-quality-v1|languages:v3|'+__import__('json').dumps(['en','th',text],ensure_ascii=False)
            translator.cache[old]='Incomplete old output'
            with patch.object(LocalTranslator,'complete',return_value=['Full new output']) as infer:
                values,hits=translator.translate([text],None,'argos-quality-v1',provider='argos',complete=LocalTranslator().complete)
                self.assertEqual((values,hits),(['Full new output'],0));infer.assert_called_once()
            values,hits=translator.translate([text],None,'argos-quality-v1',provider='argos')
            self.assertEqual((values,hits),(['Full new output'],1))

    def test_bundled_language_graph_covers_90_distinct_pairs(self):
        local=LocalTranslator();codes=local.catalog['languages']
        self.assertEqual(len(codes),10)
        for source in codes:
            for target in codes:
                path=local.route(source,target)
                if source==target:self.assertEqual(path,[])
                else:
                    self.assertEqual(path[0]['source'],source);self.assertEqual(path[-1]['target'],target)
                    self.assertLessEqual(len(path),2)
        self.assertEqual([step['target'] for step in local.route('ja','th')],['en','th'])

    def test_locale_variants_and_unsupported_languages_are_explicit(self):
        local=LocalTranslator();self.assertEqual(len(local.route('en-US','th-TH')),1)
        self.assertIsNone(local.validate_pair('auto','th'))
        with self.assertRaises(RuntimeError):local.validate_pair('auto','auto')
        for source,target in [('auto','th'),('ar','th'),('zh-Hant','th'),('en','zh-TW')]:
            with self.assertRaises(RuntimeError):local.route(source,target)

    def test_auto_detect_all_ten_bundled_languages(self):
        local=LocalTranslator()
        samples={'en':'The valley remembers you.','th':'หุบเขายังจำคุณได้','zh':'这个山谷还记得你。',
                 'ja':'この谷はあなたを覚えています。','ko':'이 계곡은 당신을 기억합니다.',
                 'fr':'La vallée se souvient de vous.','de':'Das Tal erinnert sich an dich.',
                 'es':'El valle te recuerda.','vi':'Thung lũng vẫn nhớ bạn.','ru':'Долина помнит тебя.'}
        for code,text in samples.items():
            with self.subTest(code=code):self.assertEqual(local.detector.detect(text),code)
        for text,code in [('Hello!','en'),('OK','en'),('Bonjour','fr'),('Merci!','fr'),('Hola','es'),('Danke','de')]:
            self.assertEqual(local.detector.detect(text),code)

    def test_auto_detect_mixed_batch_keeps_order_and_identity(self):
        local=LocalTranslator();texts=['Bonjour','Hello','Merci','123…','หุบเขายังจำคุณได้']
        def translate(model,values,route,deadline):return [route[0]['source']+':'+v for v in values] if route else values
        with patch.object(local,'_translate',side_effect=translate) as infer:
            self.assertEqual(local.complete(None,'argos-fast-v1',texts,source='auto',target='th'),
                             ['fr:Bonjour','en:Hello','fr:Merci','123…','หุบเขายังจำคุณได้'])
            self.assertEqual(infer.call_count,3)

    def test_auto_detect_rejects_uncertain_or_unsupported_text_before_inference(self):
        local=LocalTranslator()
        with patch.object(local,'_session',side_effect=AssertionError('Invalid language reached inference')):
            for text in ['مرحبا بك في الوادي','Questo è un testo in italiano.','Це українська мова, будь ласка.','X']:
                with self.subTest(text=text),self.assertRaisesRegex(RuntimeError,'Auto detect'):
                    local.complete(None,'argos-fast-v1',[text],source='auto',target='th')

    def test_keyless_account_and_identity_need_no_runtime(self):
        local=LocalTranslator();self.assertTrue(local.connected);self.assertNotIn('access_token',local.account)
        with patch.object(local,'_session',side_effect=AssertionError('Identity must not infer')):
            self.assertEqual(local.complete(None,'argos-fast-v1',['Bonjour'],source='fr',target='fr'),['Bonjour'])

    def test_oversized_passage_is_rejected_instead_of_truncated(self):
        local=LocalTranslator();tokenizer=SimpleNamespace(encode=lambda text:['token']*513)
        runtime=SimpleNamespace(translate_batch=lambda *a,**k:self.fail('Oversized text reached inference'))
        with patch.object(local,'_session',return_value=(runtime,tokenizer,'')):
            with self.assertRaisesRegex(RuntimeError,'not truncated'):local.complete(None,'argos-fast-v1',['Long passage'])

    def test_incomplete_output_never_enters_cache(self):
        local=LocalTranslator();tokenizer=SimpleNamespace(encode=lambda text:['token'],decode=lambda pieces:'')
        runtime=SimpleNamespace(translate_batch=lambda *a,**k:[SimpleNamespace(hypotheses=[['token']])])
        with tempfile.TemporaryDirectory(dir='.') as tmp,patch.dict(os.environ,RUEVALLEY_DATA_DIR=tmp),patch.object(local,'_session',return_value=(runtime,tokenizer,'')):
            translator=Translator()
            with self.assertRaises(RuntimeError):translator.translate(['Hello'],None,'argos-balanced-v1',provider='argos',complete=local.complete)
            self.assertEqual(translator.cache,{})

    def test_local_cache_is_separate_from_cloud(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp,patch.dict(os.environ,RUEVALLEY_DATA_DIR=tmp):
            translator=Translator()
            with patch('desktop.translation.stream_translation',return_value=['Cloud']):translator.translate(['Hello'],'token','same')
            result,hits=translator.translate(['Hello','Hello'],None,'same',provider='argos',complete=lambda *a,**k:['Local'])
            self.assertEqual(result,['Local','Local'])
            result,hits=translator.translate(['Hello'],None,'same',provider='argos');self.assertEqual((result,hits),(['Local'],1))
