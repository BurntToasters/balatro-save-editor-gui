import datetime
import os
import re
import shutil
import zlib

from .token_iterator import TokenIterator

TOKEN_RE = r'([\[\]{},="\\])'


class Struct(object):
    def __init__(self, token_iterator):
        self.token_iterator = token_iterator
        self.structs = []

    def __str__(self):
        return ''.join(map(str, self.structs))


class LiteralStruct(Struct):
    def __init__(self, token_iterator, token):
        super().__init__(token_iterator)
        self.structs.append(token)
        if token == '"':
            self.structs.extend(token_iterator.until('"'))


class MapKeyStruct(Struct):
    def __init__(self, token_iterator, token):
        super().__init__(token_iterator)
        self.structs.append(LiteralStruct(token_iterator, token))
        token = next(token_iterator)
        while not token == ']':
            self.structs.append(LiteralStruct(token_iterator, token))
            token = next(token_iterator)
        self.structs.append(LiteralStruct(token_iterator, token))
        self.structs.append(LiteralStruct(token_iterator, next(token_iterator)))


class MapValueStruct(Struct):
    def __init__(self, token_iterator, token):
        super().__init__(token_iterator)
        if token == '{':
            self.structs.append(MapStruct(token_iterator, token))
        else:
            self.structs.append(LiteralStruct(token_iterator, token))
        self.structs.append(LiteralStruct(token_iterator, next(token_iterator)))


class MapEntryStruct(Struct):
    def __init__(self, token_iterator, token):
        super().__init__(token_iterator)
        self.structs.append(MapKeyStruct(token_iterator, token))
        self.structs.append(MapValueStruct(token_iterator, next(token_iterator)))

    @property
    def key(self):
        # Handles quoted string keys (["name"]) and bare keys ([1], [-1]).
        inner = self.structs[0].structs[1].structs
        if len(inner) >= 3 and inner[0] == '"' and inner[-1] == '"':
            return ''.join(inner[1:-1])
        return ''.join(str(t) for t in inner)

    @property
    def value(self):
        return self.structs[1].structs[0]

    def set_int_key(self, n):
        self.structs[0].structs[1].structs = [str(n)]


class MapStruct(Struct):
    def __init__(self, token_iterator, token):
        super().__init__(token_iterator)
        self.structs.append(LiteralStruct(token_iterator, token))
        while True:
            token = next(token_iterator)
            if token == '}':
                self.structs.append(LiteralStruct(token_iterator, token))
                return
            elif token == '[':
                self.structs.append(MapEntryStruct(token_iterator, token))
            else:
                self.structs.append(LiteralStruct(token_iterator, token))
                continue

    def __getitem__(self, key):
        for struct in self.structs:
            if not isinstance(struct, MapEntryStruct):
                continue
            if struct.key == key:
                return struct.value
        raise ValueError('No such key')

    def __setitem__(self, key, value):
        for struct in self.structs:
            if not isinstance(struct, MapEntryStruct):
                continue
            if struct.key == key:
                if not isinstance(struct.value, LiteralStruct):
                    raise ValueError('Can only set values of type LiteralStruct')
                if len(struct.value.structs) == 1:
                    struct.value.structs[0] = value
                elif len(struct.value.structs) == 3 and struct.value.structs[0] == '"' and struct.value.structs[2] == '"':
                    struct.value.structs[1] = value
                return
        raise ValueError('No such key')

    def __contains__(self, key):
        for struct in self.structs:
            if not isinstance(struct, MapEntryStruct):
                continue
            if struct.key == key:
                return True
        return False

    def __iter__(self):
        for struct in self.structs:
            if not isinstance(struct, MapEntryStruct):
                continue
            yield struct.value

    def entries(self):
        return [s for s in self.structs if isinstance(s, MapEntryStruct)]

    def entry_at(self, pos):
        return self.entries()[pos]

    def insert_entry(self, entry):
        # Insert before the closing '}' literal (always the last struct).
        self.structs.insert(len(self.structs) - 1, entry)

    def delete_entry(self, key):
        for i, struct in enumerate(self.structs):
            if isinstance(struct, MapEntryStruct) and struct.key == key:
                del self.structs[i]
                return True
        return False

    def delete_at(self, pos):
        self.structs.remove(self.entries()[pos])

    def reindex(self):
        # Renumber integer-keyed entries to 1..n (for array-like maps e.g. cards).
        i = 1
        for struct in self.structs:
            if isinstance(struct, MapEntryStruct):
                struct.set_int_key(i)
                i += 1

    def append_value(self, value_text):
        keys = [int(e.key) for e in self.entries() if e.key.lstrip('-').isdigit()]
        n = (max(keys) + 1) if keys else 1
        self.insert_entry(make_entry(f'[{n}]={value_text},'))
        return n


class BalatroSaveFile(object):
    def __init__(self, save_file_path):
        self.save_file_path = save_file_path
        self.save_file_data = self.read(self.save_file_path)
        self.structs = []

        text = str(self.decompress(self.save_file_data), encoding='ascii')
        tokens = re.split(TOKEN_RE, text)
        token_iterator = TokenIterator(tokens)

        self.structs.append(LiteralStruct(token_iterator, next(token_iterator)))
        self.structs.append(MapStruct(token_iterator, next(token_iterator)))
        self.validate()

    @staticmethod
    def read(save_file_path):
        with open(save_file_path, 'rb') as save_file:
            return save_file.read()

    def create_backup(self):
        now = str(datetime.datetime.now()).replace(' ', 'T').replace(':', '')
        save_file_name = os.path.basename(self.save_file_path)
        save_file_directory = os.path.dirname(self.save_file_path)
        save_file_backup_name = save_file_name + f'{now}.bak'
        save_file_backup_path = os.path.join(save_file_directory, save_file_backup_name)
        shutil.copy(self.save_file_path, save_file_backup_path)

    def write(self, create_backup=True, dry_run=True):
        save_file_data = self.compress(bytes(str(self), 'ascii'))
        if create_backup:
            self.create_backup()
        if not dry_run:
            with open(self.save_file_path, 'wb') as f:
                f.write(save_file_data)

    @staticmethod
    def decompress(save_file_data):
        return zlib.decompress(save_file_data, wbits=-zlib.MAX_WBITS)

    @staticmethod
    def compress(save_file_data):
        return zlib.compress(save_file_data, level=1, wbits=-zlib.MAX_WBITS)

    # Checks recompress (no changes) returns to initial file
    def validate(self):
        if not self.save_file_data == self.compress(bytes(str(self), 'ascii')):
            raise Exception('Decompression and Recompression failed!')

    def __str__(self):
        return ''.join(map(str, self.structs))

    def __getitem__(self, name):
        return self.structs[1][name]


def make_entry(text):
    """Build a MapEntryStruct from a serialized entry like '["k"]=v,' (trailing comma required)."""
    token_iterator = TokenIterator(re.split(TOKEN_RE, text))
    return MapEntryStruct(token_iterator, next(token_iterator))
