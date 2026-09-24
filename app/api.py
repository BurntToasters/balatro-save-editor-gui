import hashlib
import os
import subprocess
import sys
import threading

from . import __version__, paths, resources, settings, updates
from .editor import BalatroSaveEditor, JokerEditor, joker_catalog


def _disk_stamp(path):
    """Hash of the file's bytes, or None when it can't be read (e.g. Balatro deleted it).

    Content, not mtime: exFAT/FAT only keep 2-second timestamps, and saves are a few KB.
    """
    try:
        with open(path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


class Api:
    """Bridge exposed to the web frontend via pywebview."""

    def __init__(self, window=None, debug=False):
        self._window = window
        self._debug = debug
        self.editor = None
        self.save_path = None
        self._stamp = None  # disk stamp of save_path when it was last read or written
        self._dirty = False  # the page has unsaved edits (it reports every change)
        self._force_close = False
        self._asking_close = False

    # ---- window ----

    def set_dirty(self, dirty):
        self._dirty = bool(dirty)
        return True

    def on_closing(self):
        # window.events.closing: returning False keeps the window open.
        # pywebview calls this on the GUI thread, and on macOS/GTK a confirmation dialog waits
        # for that same thread, so asking here would freeze. Cancel now, ask from a worker,
        # and close for real if the user says yes.
        if self._force_close or not self._dirty or self._window is None:
            return True
        if not self._asking_close:
            self._asking_close = True
            threading.Thread(target=self._confirm_close, daemon=True).start()
        return False

    def _confirm_close(self):
        try:
            discard = self._window.create_confirmation_dialog(
                'Discard changes?', 'You have unsaved changes. Close Balatro Save Editor and discard them?'
            )
        finally:
            self._asking_close = False
        if discard:
            self._force_close = True
            self._window.destroy()

    def ui_ready(self):
        # Window starts hidden so the first paint isn't a csgo flashbang.
        if self._window is not None:
            self._window.show()
        return True

    def confirm(self, title, message):
        if self._window is None:
            return True
        return bool(self._window.create_confirmation_dialog(str(title), str(message)))

    def restart(self):
        # Start a fresh copy of the app, then close this one.
        if getattr(sys, 'frozen', False):
            argv, cwd = [sys.executable], None
        else:
            argv, cwd = [sys.executable, '-m', 'app.main'], resources.resource_base()
        kwargs = {'cwd': cwd, 'close_fds': True}
        if sys.platform.startswith('win'):
            kwargs['creationflags'] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs['start_new_session'] = True
        try:
            subprocess.Popen(argv, **kwargs)
        except OSError as e:
            return {'ok': False, 'error': f'Could not restart: {e}'}
        if self._window is not None:
            self._force_close = True  # the page already warned about unsaved changes
            self._window.destroy()
        return {'ok': True}

    # ---- info ----

    def app_info(self):
        return {
            'version': __version__,
            'debug': self._debug,
            'settings': settings.load(),
            'settings_path': str(settings.path()),
        }

    # ---- updates ----

    def check_for_updates(self):
        return updates.check()

    # ---- settings ----

    def set_setting(self, key, value):
        try:
            return {'ok': True, 'settings': settings.save({key: value})}
        except (OSError, ValueError) as e:
            return {'ok': False, 'error': str(e)}

    def reset_settings(self):
        try:
            return {'ok': True, 'settings': settings.reset()}
        except OSError as e:
            return {'ok': False, 'error': str(e)}

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
            if not os.path.exists(path):
                raise FileNotFoundError(
                    'This save file is gone. Balatro deletes save.jkr when a run ends; '
                    'start a run to make a new one.'
                )
            # Stamp before reading: if Balatro writes mid-read, the next check sees a change.
            stamp = _disk_stamp(path)
            self.editor = BalatroSaveEditor(path)
            self.save_path = path
            self._stamp = stamp
            # Editions set by editor 1.0.0/1.0.1 lack their effect; fix in memory, saved on Save.
            try:
                repaired = self._joker_editor().repair_editions()
            except Exception:
                repaired = 0  # no joker area (e.g. not a run save): nothing to repair
            return {'ok': True, 'state': self.get_state(), 'repaired': repaired}
        except Exception as e:
            self.editor = None
            self.save_path = None
            self._stamp = None
            return {'ok': False, 'error': str(e)}

    def save_status(self):
        """Has the loaded save changed on disk (e.g. Balatro wrote it) since we read it?"""
        if self.editor is None:
            return {'loaded': False, 'changed': False, 'missing': False}
        now = _disk_stamp(self.save_path)
        return {'loaded': True, 'changed': now != self._stamp, 'missing': now is None}

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

    def save(self, create_backup=True, overwrite=False):
        if self.editor is None:
            return {'ok': False, 'error': 'No save loaded.'}
        status = self.save_status()
        if status['changed'] and not overwrite:
            return {
                'ok': False,
                'conflict': True,
                'missing': status['missing'],
                'error': 'Balatro updated this save since you opened it.',
            }
        try:
            # A save Balatro deleted (run ended) has nothing to back up.
            backup = create_backup and not status['missing']
            self.editor.balatro_save_file.write(create_backup=backup, dry_run=False)
            # Reload from disk: re-runs validate() to confirm the written file round-trips.
            stamp = _disk_stamp(self.save_path)
            self.editor = BalatroSaveEditor(self.save_path)
            self._stamp = stamp
            return {'ok': True, 'state': self.get_state(), 'backed_up': backup}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    # ---- jokers ----

    def joker_catalog(self):
        return joker_catalog.CATALOG

    def _joker_editor(self):
        return JokerEditor(self.editor.balatro_save_file)

    def get_jokers(self):
        if self.editor is None:
            return {'ok': False, 'error': 'No save loaded.'}
        try:
            return {'ok': True, 'jokers': self._joker_editor().list_jokers()}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def _joker_op(self, fn):
        if self.editor is None:
            return {'ok': False, 'error': 'No save loaded.'}
        try:
            je = self._joker_editor()
            fn(je)
            return {'ok': True, 'jokers': je.list_jokers()}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def joker_set_edition(self, index, edition):
        return self._joker_op(lambda je: je.set_edition(int(index), edition or None))

    def joker_set_sticker(self, index, sticker, on):
        return self._joker_op(lambda je: je.set_sticker(int(index), sticker, bool(on)))

    def joker_set_sell(self, index, value):
        return self._joker_op(lambda je: je.set_sell(int(index), value))

    def joker_duplicate(self, index):
        return self._joker_op(lambda je: je.duplicate_joker(int(index)))

    def joker_delete(self, index):
        return self._joker_op(lambda je: je.delete_joker(int(index)))

    def joker_set_type(self, index, center, name):
        return self._joker_op(lambda je: je.set_joker_type(int(index), center, name))

    def joker_add(self, center, name):
        return self._joker_op(lambda je: je.add_joker(center, name))

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
