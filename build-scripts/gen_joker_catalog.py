"""Regenerate app/editor/joker_catalog.py from the Balatro wiki Jokers data.

Fetches Module:Jokers/data (Lua), parses it, and writes the catalog with each
joker's name, rarity, order, cost, set and config. Run: python build-scripts/gen_joker_catalog.py
"""
import os
import re
import urllib.request

URL = 'https://balatrowiki.org/index.php?title=Module:Jokers/data&action=raw'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'editor', 'joker_catalog.py')


# ---- tiny Lua-table-literal parser (enough for this data) ----

def skip_ws(s, i):
    while i < len(s) and s[i] in ' \t\r\n':
        i += 1
    return i


def parse_string(s, i):
    assert s[i] == '"'
    i += 1
    out = []
    while s[i] != '"':
        out.append(s[i])
        i += 1
    return ''.join(out), i + 1


def parse_number(s, i):
    m = re.match(r'-?\d+\.?\d*', s[i:])
    tok = m.group(0)
    val = float(tok) if ('.' in tok) else int(tok)
    return val, i + len(tok)


def parse_value(s, i):
    i = skip_ws(s, i)
    c = s[i]
    if c == '{':
        return parse_table(s, i)
    if c == '"':
        return parse_string(s, i)
    if c == '-' or c.isdigit():
        return parse_number(s, i)
    word = re.match(r'[A-Za-z_][A-Za-z0-9_]*', s[i:]).group(0)
    i += len(word)
    if word == 'true':
        return True, i
    if word == 'false':
        return False, i
    if word == 'nil':
        return None, i
    return word, i


def parse_table(s, i):
    assert s[i] == '{'
    i += 1
    result = {}
    arr_idx = 1
    while True:
        i = skip_ws(s, i)
        if s[i] == '}':
            return result, i + 1
        key = None
        if s[i] == '[':
            i = skip_ws(s, i + 1)
            if s[i] == '"':
                key, i = parse_string(s, i)
            else:
                key, i = parse_number(s, i)
            i = skip_ws(s, i)
            i += 1  # ]
            i = skip_ws(s, i)
            i += 1  # =
            i, key_set = skip_ws(s, i), True
            val, i = parse_value(s, i)
        else:
            j = i
            while s[j].isalnum() or s[j] == '_':
                j += 1
            k = skip_ws(s, j)
            if k < len(s) and s[k] == '=' and s[k + 1] != '=':
                key = s[i:j]
                i = skip_ws(s, k + 1)
                val, i = parse_value(s, i)
            else:
                key = arr_idx
                arr_idx += 1
                val, i = parse_value(s, i)
        result[key] = val
        i = skip_ws(s, i)
        if i < len(s) and s[i] == ',':
            i += 1


def main():
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0 (catalog-generator)'})
    raw = urllib.request.urlopen(req, timeout=30).read().decode('utf-8')
    start = raw.index('return')
    brace = raw.index('{', start)
    data, _ = parse_table(raw, brace)

    jokers = sorted(data.items(), key=lambda kv: kv[1].get('order', 9999))
    rarities = {1: 'Common', 2: 'Uncommon', 3: 'Rare', 4: 'Legendary'}

    lines = [
        '# Joker center keys -> display name, rarity, order, cost, set, config.',
        '# Generated from the Balatro Wiki Module:Jokers/data. Regenerate with:',
        '#   python build-scripts/gen_joker_catalog.py',
        'RARITIES = {1: \'Common\', 2: \'Uncommon\', 3: \'Rare\', 4: \'Legendary\'}',
        '',
        '_JOKERS = [',
    ]
    for key, j in jokers:
        entry = {
            'key': key,
            'name': j.get('name', key),
            'rarity': j.get('rarity', 1),
            'order': j.get('order', 0),
            'cost': j.get('cost', 0),
            'set': j.get('set', 'Joker'),
            'config': j.get('config', {}),
        }
        lines.append(f'    {entry!r},')
    lines += [
        ']',
        '',
        "CATALOG = [{'key': j['key'], 'name': j['name'], 'rarity': j['rarity'],",
        "            'rarity_name': RARITIES.get(j['rarity'], 'Common')} for j in _JOKERS]",
        "NAMES = {j['key']: j['name'] for j in _JOKERS}",
        "CONFIGS = {j['key']: j for j in _JOKERS}",
        '',
        '',
        'def name_for(center):',
        '    return NAMES.get(center, center)',
        '',
    ]
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'Wrote {OUT} with {len(jokers)} jokers')


if __name__ == '__main__':
    main()
