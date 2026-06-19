from app.editor import BalatroSaveFile
from app.editor.save_file import make_entry


def roundtrip(bsf, tmp_path):
    """Recompress edited content and reload it (constructor runs byte-exact validate())."""
    edited = str(bsf)
    p = tmp_path / 'edited.jkr'
    p.write_bytes(BalatroSaveFile.compress(bytes(edited, 'ascii')))
    reloaded = BalatroSaveFile(str(p))
    assert str(reloaded) == edited
    return reloaded


def cards_of(bsf):
    return bsf['cardAreas']['jokers']['cards']


def test_integer_key_resolves(sample_save):
    bsf = BalatroSaveFile(str(sample_save))
    keys = [e.key for e in cards_of(bsf).entries()]
    assert keys == ['1', '2']


def test_insert_entry_into_string_map(sample_save, tmp_path):
    bsf = BalatroSaveFile(str(sample_save))
    bsf['GAME'].insert_entry(make_entry('["newk"]=5,'))
    reloaded = roundtrip(bsf, tmp_path)
    assert 'newk' in reloaded['GAME']
    assert str(reloaded['GAME']['newk']) == '5'


def test_append_value_and_reindex(sample_save, tmp_path):
    bsf = BalatroSaveFile(str(sample_save))
    cards = cards_of(bsf)
    before = len(cards.entries())
    n = cards.append_value('{["ability"]={["name"]="Added",},}')
    assert n == before + 1
    cards.reindex()
    reloaded = roundtrip(bsf, tmp_path)
    rcards = cards_of(reloaded)
    assert [e.key for e in rcards.entries()] == ['1', '2', '3']


def test_delete_at_and_reindex(sample_save, tmp_path):
    bsf = BalatroSaveFile(str(sample_save))
    cards = cards_of(bsf)
    cards.delete_at(0)
    cards.reindex()
    reloaded = roundtrip(bsf, tmp_path)
    rcards = cards_of(reloaded)
    assert [e.key for e in rcards.entries()] == ['1']


def test_insert_nested_subtable(sample_save, tmp_path):
    bsf = BalatroSaveFile(str(sample_save))
    first = next(iter(cards_of(bsf)))
    first.insert_entry(make_entry('["edition"]={["holo"]=true,},'))
    reloaded = roundtrip(bsf, tmp_path)
    rfirst = next(iter(cards_of(reloaded)))
    assert 'edition' in rfirst
    assert 'holo' in rfirst['edition']


def test_delete_entry_by_key(sample_save, tmp_path):
    bsf = BalatroSaveFile(str(sample_save))
    assert bsf['GAME'].delete_entry('chips_text') is True
    reloaded = roundtrip(bsf, tmp_path)
    assert 'chips_text' not in reloaded['GAME']
