import unittest
from unittest.mock import Mock, patch
from desktop.translation import Translator


class CacheTests(unittest.TestCase):
    @patch('desktop.translation.write_json')
    @patch('desktop.translation.read_json',return_value={})
    @patch('desktop.translation.stream_translation',return_value=['translated'])
    def test_repeat_capture_skips_network_and_auth(self,stream,read,write):
        translator=Translator()
        token=Mock(return_value='private-test-token')
        self.assertEqual(translator.translate(['dialogue'],token,'model'),(['translated'],0))
        self.assertEqual(translator.translate(['dialogue'],token,'model'),(['translated'],1))
        token.assert_called_once_with()
        self.assertEqual(stream.call_count,1)

    @patch('desktop.translation.write_json')
    @patch('desktop.translation.read_json',return_value={'model|th:v2|dialogue':'old'})
    @patch('desktop.translation.stream_translation',return_value=['fresh'])
    def test_disabled_cache_respects_timeout_and_does_not_write(self,stream,read,write):
        translator=Translator(); translator.cache_enabled=False; translator.timeout=60
        self.assertEqual(translator.translate(['dialogue','dialogue'],'token','model'),(['fresh','fresh'],0))
        stream.assert_called_once_with('token','model',['dialogue'],timeout=60)
        write.assert_not_called()
