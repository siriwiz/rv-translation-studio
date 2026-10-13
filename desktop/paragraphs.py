"""Reconstruct wrapped dialogue before translation, retaining every OCR word box."""
import re
from .colors import compatible_colors
from .languages import is_rtl


def _join(a, b):
    # OCR often splits a word at a printed line-ending hyphen.
    if re.search(r'[A-Za-z]-$', a) and re.match(r'^[a-z]', b):
        return a[:-1] + b
    compact=r'[\u0e00-\u0e7f\u3040-\u30ff\u3400-\u9fff]'
    separator='' if re.search(compact+'$',a.rstrip()) and re.match(compact,b.lstrip()) else ' '
    return re.sub(r'\s+([,.;:!?，。！？、])', r'\1', a.rstrip() + separator + b.lstrip())


def _merge(a, b):
    right = max(a['x'] + a['w'], b['x'] + b['w'])
    bottom = max(a['y'] + a['h'], b['y'] + b['h'])
    a['text'] = _join(a['text'], b['text'])
    a['words'] += b['words']
    a['x'], a['y'] = min(a['x'], b['x']), min(a['y'], b['y'])
    a['w'], a['h'] = right - a['x'], bottom - a['y']
    a['source_lines'] += b['source_lines']
    if 'glyph_masks' in a or 'glyph_masks' in b:
        a.setdefault('glyph_masks',[]).extend(b.get('glyph_masks',[]))
    return a


def group_dialogue(lines,language='en'):
    rtl=is_rtl(language,lines[0]['text'] if lines else '')
    rows = []
    for original in sorted(lines, key=lambda l: (l['y'], -l['x'] if rtl else l['x'])):
        item = dict(original)
        item['text'] = re.sub(r'\s+', ' ', item['text']).strip()
        words = item.get('words')
        item['words'] = list(words) if isinstance(words, list) else ([words] if isinstance(words, dict) else [])
        if not item['words']:
            item['words'] = [{k: item[k] for k in ('x', 'y', 'w', 'h')}]
        item.update(line_height=item['h'], source_lines=1)
        # Join nearby fragments on the same baseline; never bridge wide UI columns.
        same = next((r for r in reversed(rows)
                     if abs(r['y'] - item['y']) <= min(r['h'], item['h']) * .35
                     and compatible_colors(r, item)
                     and 0 <= (r['x']-(item['x']+item['w']) if rtl else item['x']-(r['x']+r['w'])) <= item['h'] * 1.8), None)
        if same:
            _merge(same, item)
            same['source_lines'] = 1
        else:
            rows.append(item)
    blocks = []
    for row in sorted(rows, key=lambda l: (l['y'], l['x'])):
        candidates = []
        for block in blocks:
            h = block['line_height']
            gap = row['y'] - (block['y'] + block['h'])
            aligned = (abs(row['x'] - block['x']) <= h * 1.5 or
                       abs(row['x'] + row['w']/2 - block['x'] - block['w']/2) <= h)
            # Short labels and complete sentences are independent UI entries.
            compact=bool(re.search(r'[\u0e00-\u0e7f\u3040-\u30ff\u3400-\u9fff]',block['text']))
            long_enough=(len(block['text'])>=8 and len(row['text'])>=3) if compact else (len(block['text'].split())>=4 and len(row['text'].split())>=2)
            continuation = long_enough and not re.search(r'[.!?。！？][\"\u201d\u2019」』]?$', block['text'])
            if (-h * .15 <= gap <= h * .85 and .65 <= row['h']/h <= 1.5
                    and aligned and continuation and compatible_colors(block, row) and block['source_lines'] < 6):
                candidates.append((abs(gap), abs(row['x'] - block['x']), block))
        if candidates:
            _merge(min(candidates, key=lambda c: c[:2])[2], row)
        else:
            blocks.append(row)
    return sorted(blocks, key=lambda l: (l['y'], l['x']))
