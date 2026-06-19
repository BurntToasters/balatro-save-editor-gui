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


# Minimal save whose single joker has the full real-card field set (incl. params).
_PARAM_SAVE = (
    'return{["cardAreas"]={["jokers"]={["config"]={["card_count"]=1,},'
    '["cards"]={[1]={'
    '["ability"]={["name"]="Riff-raff",["eternal"]=true,["set"]="Joker",},'
    '["params"]={["bypass_discovery_center"]=true,["bypass_back"]={["x"]=1,["y"]=2,},},'
    '["save_fields"]={["center"]="j_riff_raff",},'
    '["edition"]={["foil"]=true,},["sell_cost"]=3,'
    '},},},},}'
)


def _build_save(tmp_path, text):
    p = tmp_path / 'save.jkr'
    p.write_bytes(BalatroSaveFile.compress(bytes(text, 'ascii')))
    return p


def _card_has(bsf, index, key):
    cards = list(bsf['cardAreas']['jokers']['cards'])
    return key in cards[index]


def test_added_joker_has_params_via_template(sample_save, tmp_path):
    # Remove all jokers so add falls back to the template, then verify params.
    je = editor(sample_save)
    je.delete_joker(0)
    je.delete_joker(0)
    je.add_joker('j_dna', 'DNA')
    je = reload_editor(je, tmp_path)
    assert _card_has(je.save_file, 0, 'params')


def test_added_joker_clones_params_and_strips_cosmetics(tmp_path):
    bsf = BalatroSaveFile(str(_build_save(tmp_path, _PARAM_SAVE)))
    je = JokerEditor(bsf)
    je.add_joker('j_blueprint', 'Blueprint')

    p = tmp_path / 'edited.jkr'
    p.write_bytes(BalatroSaveFile.compress(bytes(str(bsf), 'ascii')))
    reloaded = BalatroSaveFile(str(p))
    je2 = JokerEditor(reloaded)

    jokers = je2.list_jokers()
    assert len(jokers) == 2
    added = jokers[-1]
    assert added['center'] == 'j_blueprint'
    assert _card_has(reloaded, 1, 'params')      # cloned structural field present
    assert added['edition'] is None              # cosmetics cleared
    assert added['stickers'] == []


def _ability(bsf, index):
    return list(bsf['cardAreas']['jokers']['cards'])[index]['ability']


def test_add_joker_uses_target_config(sample_save, tmp_path):
    je = editor(sample_save)
    je.add_joker('j_throwback', 'Throwback')
    je = reload_editor(je, tmp_path)
    ab = _ability(je.save_file, len(je.list_jokers()) - 1)
    assert str(ab['extra']) == '0.25'        # Throwback's per-skip X mult
    assert str(ab['name']) == '"Throwback"'
    assert str(ab['x_mult']) == '1'


def test_add_joker_sets_flat_mult(sample_save, tmp_path):
    je = editor(sample_save)
    je.add_joker('j_joker', 'Joker')
    je = reload_editor(je, tmp_path)
    assert str(_ability(je.save_file, len(je.list_jokers()) - 1)['mult']) == '4'


def test_add_joker_nested_config(sample_save, tmp_path):
    je = editor(sample_save)
    je.add_joker('j_greedy_joker', 'Greedy Joker')
    je = reload_editor(je, tmp_path)
    extra = _ability(je.save_file, len(je.list_jokers()) - 1)['extra']
    assert 's_mult' in extra and str(extra['s_mult']) == '3'
    assert str(extra['suit']) == '"Diamonds"'


def test_set_joker_type_rebuilds_ability(sample_save, tmp_path):
    je = editor(sample_save)
    je.set_joker_type(0, 'j_jolly', 'Jolly Joker')
    je = reload_editor(je, tmp_path)
    ab = _ability(je.save_file, 0)
    assert str(ab['t_mult']) == '8'
    assert str(ab['type']) == '"Pair"'
    assert je.list_jokers()[0]['name'] == 'Jolly Joker'
