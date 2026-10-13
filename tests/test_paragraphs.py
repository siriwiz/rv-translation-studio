import unittest
from desktop.paragraphs import group_dialogue


def line(text, x=40, y=40, w=420, h=24):
    return dict(text=text, x=x, y=y, w=w, h=h,
                words=[dict(x=x, y=y, w=w, h=h)])


class ParagraphTests(unittest.TestCase):
    def test_wraps_in_reading_order_and_preserves_inpaint_masks(self):
        inputs = [line('where we first met.', y=104),
                  line('I still remember the night', y=40),
                  line('you came back to the place', y=72)]
        output = group_dialogue(inputs)
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]['text'], 'I still remember the night you came back to the place where we first met.')
        self.assertEqual(output[0]['source_lines'], 3)
        self.assertEqual(output[0]['line_height'], 24)
        self.assertEqual(output[0]['h'], 88)
        self.assertEqual(len(output[0]['words']), 3)
        self.assertNotIn('source_lines', inputs[0])

    def test_separate_columns_menus_and_finished_sentences(self):
        for inputs in ([line('New game'), line('Load game', y=72)],
                       [line('This is a complete sentence.'), line('And another one begins.', y=72)],
                       [line('I still remember the night', w=300), line('you came back to me', x=650, y=72)],
                       [line('I still remember the night'), line('you came back to me', y=140)]):
            with self.subTest(inputs=inputs):
                self.assertEqual(len(group_dialogue(inputs)), 2)

    def test_same_row_fragments_and_hyphenated_word(self):
        output = group_dialogue([line('I remember that extraor-', w=300),
                                line('dinary night we met.', y=72)])
        self.assertEqual(output[0]['text'], 'I remember that extraordinary night we met.')
        output = group_dialogue([line('Where are', w=100), line('you going?', x=155, w=130)])
        self.assertEqual(output[0]['text'], 'Where are you going?')


if __name__ == '__main__':
    unittest.main()
