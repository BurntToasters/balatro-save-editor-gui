from app.editor import BalatroSaveEditor, BalatroSaveFile


def test_parse_round_trips(sample_save, sample_text):
    bsf = BalatroSaveFile(str(sample_save))
    # str() must reproduce the decompressed body byte-for-byte
    assert str(bsf) == sample_text


def test_presets_apply_and_persist(sample_save):
    editor = BalatroSaveEditor(str(sample_save))
    editor.edit_money(19999)
    editor.edit_chips()
    editor.edit_multipliers()
    editor.edit_card_limits()
    editor.edit_card_abilities()
    editor.balatro_save_file.write(create_backup=False, dry_run=False)

    bsf = BalatroSaveFile(str(sample_save))
    assert str(bsf['GAME']['dollars']) == '19999'
    assert str(bsf['GAME']['chips']) == '299'

    mults = [str(hand['mult']) for hand in bsf['GAME']['hands']]
    assert mults == ['10000', '10000']

    jokers_cfg = bsf['cardAreas']['jokers']['config']
    assert str(jokers_cfg['card_limit']) == '20'
    assert str(jokers_cfg['temp_limit']) == '20'

    cons_cfg = bsf['cardAreas']['consumeables']['config']
    assert str(cons_cfg['card_limit']) == '10'

    for joker in bsf['cardAreas']['jokers']['cards']:
        if 'eternal' in joker['ability']:
            assert str(joker['ability']['eternal']) == 'false'


def test_custom_card_limits(sample_save):
    editor = BalatroSaveEditor(str(sample_save))
    editor.edit_card_limits(joker_limit=8, consumable_limit=4)
    editor.balatro_save_file.write(create_backup=False, dry_run=False)

    bsf = BalatroSaveFile(str(sample_save))
    assert str(bsf['cardAreas']['jokers']['config']['card_limit']) == '8'
    assert str(bsf['cardAreas']['consumeables']['config']['card_limit']) == '4'
