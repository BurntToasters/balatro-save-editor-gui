from app.editor import BalatroSaveFile, JokerEditor


def reload_editor(je, tmp_path):
    """Round-trip the edited save through compress/parse (byte-exact validate) and rewrap."""
    edited = str(je.save_file)
    p = tmp_path / 'edited.jkr'
    p.write_bytes(BalatroSaveFile.compress(bytes(edited, 'ascii')))
    reloaded = BalatroSaveFile(str(p))
    assert str(reloaded) == edited
    return JokerEditor(reloaded)


def editor(sample_save):
    return JokerEditor(BalatroSaveFile(str(sample_save)))


def test_list_jokers(sample_save):
    jokers = editor(sample_save).list_jokers()
    assert len(jokers) == 2
    assert jokers[0]['name'] == 'Joker'
    assert jokers[0]['stickers'] == ['eternal']
    assert jokers[1]['stickers'] == []


def test_set_edition_add_and_clear(sample_save, tmp_path):
    je = editor(sample_save)
    je.set_edition(0, 'foil')
    je = reload_editor(je, tmp_path)
    assert je.list_jokers()[0]['edition'] == 'foil'

    je.set_edition(0, 'negative')
    je = reload_editor(je, tmp_path)
    assert je.list_jokers()[0]['edition'] == 'negative'

    je.set_edition(0, None)
    je = reload_editor(je, tmp_path)
    assert je.list_jokers()[0]['edition'] is None


def test_set_sticker(sample_save, tmp_path):
    je = editor(sample_save)
    je.set_sticker(0, 'eternal', False)   # existing -> false
    je.set_sticker(1, 'perishable', True)  # absent -> insert
    je = reload_editor(je, tmp_path)
    jokers = je.list_jokers()
    assert 'eternal' not in jokers[0]['stickers']
    assert 'perishable' in jokers[1]['stickers']


def test_set_sell(sample_save, tmp_path):
    je = editor(sample_save)
    je.set_sell(0, 99)
    je = reload_editor(je, tmp_path)
    assert je.list_jokers()[0]['sell_cost'] == '99'


def test_duplicate_joker(sample_save, tmp_path):
    je = editor(sample_save)
    je.duplicate_joker(0)
    je = reload_editor(je, tmp_path)
    assert len(je.list_jokers()) == 3


def test_delete_joker(sample_save, tmp_path):
    je = editor(sample_save)
    je.delete_joker(0)
    je = reload_editor(je, tmp_path)
    jokers = je.list_jokers()
    assert len(jokers) == 1


def test_add_joker(sample_save, tmp_path):
    je = editor(sample_save)
    je.add_joker('j_blueprint', 'Blueprint')
    je = reload_editor(je, tmp_path)
    jokers = je.list_jokers()
    assert len(jokers) == 3
    added = jokers[-1]
    assert added['center'] == 'j_blueprint'
    assert added['name'] == 'Blueprint'


def test_set_joker_type(sample_save, tmp_path):
    je = editor(sample_save)
    je.set_joker_type(1, 'j_dna', 'DNA')
    je = reload_editor(je, tmp_path)
    j = je.list_jokers()[1]
    assert j['center'] == 'j_dna'
    assert j['name'] == 'DNA'


def test_add_joker_sanitizes_quotes(sample_save, tmp_path):
    je = editor(sample_save)
    je.add_joker('j_x"; evil', 'Bad"Name')
    # Must still round-trip (quotes stripped, not breaking the literal).
    je = reload_editor(je, tmp_path)
    assert je.list_jokers()[-1]['center'] == 'j_x; evil'
