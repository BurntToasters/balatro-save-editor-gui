from .joker_catalog import CONFIGS
from .save_file import make_entry

# Internal card.edition keys.
EDITIONS = ('foil', 'holo', 'polychrome', 'negative')
STICKERS = ('eternal', 'perishable', 'rental')

# The whole card.edition table Balatro's Card:set_edition writes (card.lua), with the values
# from game.lua's e_foil / e_holo / e_polychrome config.extra. Scoring reads the value
# (get_edition) and the tooltip badge reads `type`; the flag alone only draws the shader.
EDITION_TABLES = {
    'foil': '{["chips"]=50,["foil"]=true,["type"]="foil",}',
    'holo': '{["mult"]=10,["holo"]=true,["type"]="holo",}',
    'polychrome': '{["x_mult"]=1.5,["polychrome"]=true,["type"]="polychrome",}',
    'negative': '{["negative"]=true,["type"]="negative",}',
}

# Standard ability fields present on every joker (mirrors what Balatro writes);
# the target joker's config is overlaid on top.
_ABILITY_BASE = {
    'mult': 0, 't_mult': 0, 'h_mult': 0, 'h_x_mult': 0, 'x_mult': 1, 't_chips': 0,
    'h_dollars': 0, 'p_dollars': 0, 'h_size': 0, 'd_size': 0,
    'extra': 0, 'extra_value': 0, 'perma_bonus': 0, 'bonus': 0, 'type': '',
}

# Neutral fallback card used when adding a joker with no existing card to clone.
# Mirrors the full field set Balatro writes (incl. params / bypass_* flags) so
# the game doesn't crash indexing a missing field on load.
TEMPLATE_JOKER = (
    '{'
    '["ability"]={["name"]="Joker",["mult"]=0,["t_mult"]=0,["h_mult"]=0,["h_x_mult"]=0,'
    '["x_mult"]=1,["t_chips"]=0,["h_dollars"]=0,["p_dollars"]=0,["h_size"]=0,["d_size"]=0,'
    '["extra"]=0,["extra_value"]=0,["perma_bonus"]=0,["bonus"]=0,["set"]="Joker",["type"]="",["order"]=1,},'
    '["params"]={["bypass_discovery_center"]=true,["discover"]=false,["bypass_discovery_ui"]=true,'
    '["bypass_back"]={["x"]=0,["y"]=0,},},'
    '["save_fields"]={["center"]="j_joker",},'
    '["label"]="Joker",["sort_id"]=1,["cost"]=2,["base_cost"]=2,["sell_cost"]=1,["extra_cost"]=0,'
    '["facing"]="front",["sprite_facing"]="front",["debuff"]=false,["rank"]=1,["added_to_deck"]=true,'
    '["bypass_discovery_ui"]=true,["bypass_discovery_center"]=true,["bypass_lock"]=true,'
    '["base"]={["face_nominal"]=0,["times_played"]=0,["nominal"]=0,["suit_nominal"]=0,},'
    '}'
)


def _clean(text):
    # Strip characters that would break the serialized string literal.
    return str(text).replace('\\', '').replace('"', '')


def _strval(node):
    # Read a value struct as a plain string, dropping surrounding quotes.
    s = str(node)
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def _lua(value):
    # Serialize a Python value to Balatro's Lua-table text form.
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            key = f'[{k}]' if isinstance(k, int) else f'["{_clean(k)}"]'
            parts.append(f'{key}={_lua(v)},')
        return '{' + ''.join(parts) + '}'
    return f'"{_clean(value)}"'


def _ability_text(center, name):
    # Build a fresh ability block for a joker type from its config so per-joker
    # values (e.g. Throwback's 0.25 X mult per skip) are correct.
    info = CONFIGS.get(center, {})
    ability = dict(_ABILITY_BASE)
    ability['name'] = name
    ability['set'] = info.get('set', 'Joker')
    ability['order'] = info.get('order', 0)
    for k, v in (info.get('config') or {}).items():
        ability['x_mult' if k == 'Xmult' else k] = v
    return _lua(ability)


class JokerEditor(object):
    def __init__(self, save_file):
        self.save_file = save_file

    def _jokers(self):
        return self.save_file['cardAreas']['jokers']

    def _cards(self):
        return self._jokers()['cards']

    def _card(self, pos):
        return self._cards().entry_at(pos).value

    # ---- read ----

    def list_jokers(self):
        return [self._describe(card, i) for i, card in enumerate(self._cards())]

    def _describe(self, card, index):
        ability = card['ability'] if 'ability' in card else None
        name = ''
        if ability is not None and 'name' in ability:
            name = _strval(ability['name'])
        elif 'label' in card:
            name = _strval(card['label'])

        center = ''
        if 'save_fields' in card and 'center' in card['save_fields']:
            center = _strval(card['save_fields']['center'])

        edition = self._edition_of(card)

        stickers = []
        if ability is not None:
            stickers = [s for s in STICKERS if s in ability and str(ability[s]) == 'true']

        sell = str(card['sell_cost']) if 'sell_cost' in card else None
        return {
            'index': index,
            'name': name,
            'center': center,
            'edition': edition,
            'stickers': stickers,
            'sell_cost': sell,
        }

    # ---- modify existing ----

    def set_edition(self, pos, edition):
        if edition and edition not in EDITIONS:
            raise ValueError(f'Unknown edition: {edition}')
        card = self._card(pos)
        was_negative = self._edition_of(card) == 'negative'
        card.delete_entry('edition')
        if edition:
            card.insert_entry(make_entry(f'["edition"]={EDITION_TABLES[edition]},'))
        self._negative_slot(card, int(edition == 'negative') - int(was_negative))

    def repair_editions(self):
        """Complete edition tables that hold only the flag (written by editor 1.0.0 / 1.0.1).

        Balatro always writes `type`, so a table without it came from an editor. Returns how
        many jokers were repaired; the caller saves them on the next write.
        """
        repaired = 0
        for card in self._cards():
            if 'edition' not in card or 'type' in card['edition']:
                continue
            edition = self._edition_of(card)
            if edition is None:
                continue  # unknown (modded) edition: leave it alone
            card.delete_entry('edition')
            card.insert_entry(make_entry(f'["edition"]={EDITION_TABLES[edition]},'))
            if edition == 'negative':
                self._negative_slot(card, 1)  # the old editor never added the slot
            repaired += 1
        return repaired

    def set_sticker(self, pos, sticker, on):
        if sticker not in STICKERS:
            raise ValueError(f'Unknown sticker: {sticker}')
        ability = self._card(pos)['ability']
        if sticker in ability:
            ability[sticker] = 'true' if on else 'false'
        elif on:
            ability.insert_entry(make_entry(f'["{sticker}"]=true,'))
        if sticker == 'perishable' and on and 'perish_tally' not in ability:
            # Balatro counts perishable jokers down with perish_tally; without it the
            # end-of-round check compares nil and the game errors.
            ability.insert_entry(make_entry(f'["perish_tally"]={self._perishable_rounds()},'))

    def _perishable_rounds(self):
        try:
            return int(str(self.save_file['GAME']['perishable_rounds']))
        except (ValueError, TypeError):
            return 5

    def set_sell(self, pos, value):
        card = self._card(pos)
        v = int(value)
        if 'sell_cost' in card:
            card['sell_cost'] = str(v)
        else:
            card.insert_entry(make_entry(f'["sell_cost"]={v},'))

    # ---- structural ----

    def duplicate_joker(self, pos):
        cards = self._cards()
        source = cards.entry_at(pos).value
        cards.append_value(str(source))
        cards.reindex()
        self._sync_count()
        if self._edition_of(source) == 'negative':
            self._negative_slot(source, 1)  # like add_to_deck for the copy

    def delete_joker(self, pos):
        cards = self._cards()
        card = cards.entry_at(pos).value
        if self._edition_of(card) == 'negative':
            self._negative_slot(card, -1)  # like remove_from_deck
        cards.delete_at(pos)
        cards.reindex()
        self._sync_count()

    def set_joker_type(self, pos, center, name):
        self._retarget(self._card(pos), center, name)

    def add_joker(self, center, name):
        cards = self._cards()
        entries = cards.entries()
        # Clone an existing card when available so every structural field the
        # game needs (params, base, bypass_* flags) is present; otherwise use
        # the full template. A bare hand-built card crashes Balatro on load.
        template = str(entries[0].value) if entries else TEMPLATE_JOKER
        cards.append_value(template)
        cards.reindex()
        new_card = cards.entries()[-1].value
        self._retarget(new_card, center, name)
        self._clean_added(new_card)
        self._sync_count()

    def _clean_added(self, card):
        # A cloned card carries the source joker's cosmetics; clear them so the
        # added joker starts plain.
        card.delete_entry('edition')
        if 'ability' in card:
            ability = card['ability']
            for s in STICKERS:
                if s in ability:
                    ability[s] = 'false'

    # ---- helpers ----

    def _retarget(self, card, center, name):
        center = _clean(center)
        name = _clean(name)
        if 'save_fields' in card:
            sf = card['save_fields']
            if 'center' in sf:
                sf['center'] = center
            else:
                sf.insert_entry(make_entry(f'["center"]="{center}",'))
        else:
            card.insert_entry(make_entry(f'["save_fields"]={{["center"]="{center}",}},'))
        if 'label' in card:
            card['label'] = name
        else:
            card.insert_entry(make_entry(f'["label"]="{name}",'))

        info = CONFIGS.get(center)
        if info is not None:
            # Rebuild the ability from the target joker's config (correct scaling).
            card.delete_entry('ability')
            card.insert_entry(make_entry(f'["ability"]={_ability_text(center, name)},'))
            cost = str(info.get('cost', 0))
            if 'cost' in card:
                card['cost'] = cost
            if 'base_cost' in card:
                card['base_cost'] = cost
        elif 'ability' in card and 'name' in card['ability']:
            # Unknown/modded center: keep cloned ability, just rename.
            card['ability']['name'] = name

    @staticmethod
    def _edition_of(card):
        if 'edition' not in card:
            return None
        ed = card['edition']
        for key in EDITIONS:
            if key in ed and str(ed[key]) == 'true':
                return key
        return None

    def _negative_slot(self, card, delta):
        # Balatro counts each negative joker in play as one extra joker slot
        # (set_edition / add_to_deck +1, remove_from_deck -1), and the slot count is saved.
        if not delta or 'added_to_deck' not in card or str(card['added_to_deck']) != 'true':
            return
        cfg = self._jokers()['config']
        cfg['card_limit'] = str(int(float(str(cfg['card_limit']))) + delta)

    def _sync_count(self):
        cfg = self._jokers()['config']
        if 'card_count' in cfg:
            cfg['card_count'] = str(len(self._cards().entries()))
