from . import paths, resources
from .editor import BalatroSaveEditor


class Api:
    """Bridge exposed to the web frontend via pywebview."""

    def __init__(self, window=None):
        self._window = window
        self.editor = None
        self.save_path = None

    # ---- info ----

    def get_licenses(self):
        return resources.load_licenses()

    def open_url(self, url):
        if not isinstance(url, str) or not url.startswith(('http://', 'https://')):
            return False
        import webbrowser
        webbrowser.open(url)
        return True

    # ---- discovery ----

    def detect_saves(self):
        return [
            {'path': str(p), 'label': paths.profile_label(p)}
            for p in paths.find_saves()
        ]

    def pick_file(self):
        if self._window is None:
            return None
        result = self._window.create_file_dialog(
            allow_multiple=False,
            file_types=('Balatro save (*.jkr)', 'All files (*.*)'),
        )
        if not result:
            return None
        return result[0] if isinstance(result, (list, tuple)) else result

    # ---- load / read ----

    def load_save(self, path=None):
        try:
            if path is None:
                default = paths.default_save()
                if default is None:
                    return {'ok': False, 'error': 'No Balatro save found. Use Open to pick a file.'}
                path = str(default)
            self.editor = BalatroSaveEditor(path)
            self.save_path = path
            return {'ok': True, 'state': self.get_state()}
        except Exception as e:
            self.editor = None
            self.save_path = None
            return {'ok': False, 'error': str(e)}

    def get_state(self):
        if self.editor is None:
            return {'loaded': False}
        bsf = self.editor.balatro_save_file
        return {
            'loaded': True,
            'save_path': self.save_path,
            'profile': paths.profile_label(self.save_path),
            'money': self._read(bsf, 'GAME', 'dollars'),
            'chips': self._read(bsf, 'GAME', 'chips'),
            'blind_target': self._read(bsf, 'BLIND', 'chips'),
            'joker_limit': self._read(bsf, 'cardAreas', 'jokers', 'config', 'card_limit'),
            'consumable_limit': self._read(bsf, 'cardAreas', 'consumeables', 'config', 'card_limit'),
            'hand_mults': self._hand_mults(bsf),
            'eternal_jokers': self._eternal_count(bsf),
        }

    # ---- mutate ----

    def apply(self, changes):
        if self.editor is None:
            return {'ok': False, 'error': 'No save loaded.'}
        try:
            changes = changes or {}
            if self._on(changes, 'money'):
                self.editor.edit_money(self._int(changes['money'], 'value'))
            if self._on(changes, 'chips'):
                self.editor.edit_chips()
            if self._on(changes, 'multipliers'):
                self.editor.edit_multipliers(self._int(changes['multipliers'], 'value', 10000))
            if self._on(changes, 'card_limits'):
                c = changes['card_limits']
                self.editor.edit_card_limits(
                    joker_limit=self._int(c, 'joker_limit', 20),
                    consumable_limit=self._int(c, 'consumable_limit', 10),
                )
            if self._on(changes, 'strip_eternal'):
                self.editor.edit_card_abilities()
            return {'ok': True, 'state': self.get_state()}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def save(self, create_backup=True):
        if self.editor is None:
            return {'ok': False, 'error': 'No save loaded.'}
        try:
            self.editor.balatro_save_file.write(create_backup=create_backup, dry_run=False)
            # Reload from disk: re-runs validate() to confirm the written file round-trips.
            self.editor = BalatroSaveEditor(self.save_path)
            return {'ok': True, 'state': self.get_state()}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    # ---- helpers ----

    @staticmethod
    def _read(bsf, *keys):
        try:
            node = bsf
            for k in keys:
                node = node[k]
            return str(node)
        except Exception:
            return None

    @staticmethod
    def _hand_mults(bsf):
        try:
            return sorted({int(str(h['mult'])) for h in bsf['GAME']['hands']})
        except Exception:
            return []

    @staticmethod
    def _eternal_count(bsf):
        try:
            n = 0
            for joker in bsf['cardAreas']['jokers']['cards']:
                ability = joker['ability']
                if 'eternal' in ability and str(ability['eternal']) == 'true':
                    n += 1
            return n
        except Exception:
            return 0

    @staticmethod
    def _on(changes, key):
        v = changes.get(key)
        return isinstance(v, dict) and bool(v.get('enabled', False))

    @staticmethod
    def _int(d, key, default=None):
        raw = d.get(key, default)
        if raw is None:
            raise ValueError(f'Missing value: {key}')
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ValueError(f'"{key}" must be a whole number')
