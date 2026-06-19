from .save_file import make_entry

# Internal card.edition keys.
EDITIONS = ('foil', 'holo', 'polychrome', 'negative')
STICKERS = ('eternal', 'perishable', 'rental')

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

        edition = None
        if 'edition' in card:
            ed = card['edition']
            for key in EDITIONS:
                if key in ed and str(ed[key]) == 'true':
                    edition = key
                    break

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
        card = self._card(pos)
        card.delete_entry('edition')
        if edition:
            if edition not in EDITIONS:
                raise ValueError(f'Unknown edition: {edition}')
            card.insert_entry(make_entry(f'["edition"]={{["{edition}"]=true,}},'))

    def set_sticker(self, pos, sticker, on):
        if sticker not in STICKERS:
            raise ValueError(f'Unknown sticker: {sticker}')
        ability = self._card(pos)['ability']
        if sticker in ability:
            ability[sticker] = 'true' if on else 'false'
        elif on:
            ability.insert_entry(make_entry(f'["{sticker}"]=true,'))

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
        cards.append_value(str(cards.entry_at(pos).value))
        cards.reindex()
        self._sync_count()

    def delete_joker(self, pos):
        cards = self._cards()
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
        if 'ability' in card:
            ability = card['ability']
            if 'name' in ability:
                ability['name'] = name
            else:
                ability.insert_entry(make_entry(f'["name"]="{name}",'))
        if 'label' in card:
            card['label'] = name
        else:
            card.insert_entry(make_entry(f'["label"]="{name}",'))

    def _sync_count(self):
        cfg = self._jokers()['config']
        if 'card_count' in cfg:
            cfg['card_count'] = str(len(self._cards().entries()))
