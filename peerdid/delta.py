import base64
import base58
from datetime import datetime
import hashlib
import json
from typing import Union, List

from .jsondetect import str_seems_like_json, bytes_seems_like_json


def _is_base64(txt):
    try:
        base64.urlsafe_b64decode(txt)
        return True
    except:
        return False


_bad_json = ValueError('change should be JSON str/bytes/dict, or base64 text.')

class Delta:
    """
    An immutable {change, by, when} object. Also has .hash and .encnumbasis properties that uniquely
    identify it. The values of these properties are derived only from .change; they are not
    affected by the values in .by and .when.
    """
    def __init__(self, change_json: Union[str, bytes, dict], by: List, when: str = None):
        if isinstance(change_json, str):
            if str_seems_like_json(change_json):
                self._change = base64.urlsafe_b64encode(change_json.encode('utf-8')).decode('ascii')
            elif _is_base64(change_json):
                self._change = change_json
            else:
                raise _bad_json
        elif isinstance(change_json, bytes):
            if bytes_seems_like_json(change_json):
                self._change = base64.urlsafe_b64encode(change_json).decode('ascii')
            elif _is_base64(change_json):
                self._change = change_json.decode('ascii')
            else:
                raise _bad_json
        elif isinstance(change_json, dict):
            self._change = base64.urlsafe_b64encode(json.dumps(change_json, indent=2).encode('utf-8')).decode('ascii')
        else:
            raise _bad_json
        self._by = by
        if when is None:
            when = datetime.utcnow().isoformat()
        self._when = when
        self._hash = None

    @property
    def hash(self) -> str:
        """
        The raw bytes, unencoded, that uniquely identify this delta.
        """
        if not self._hash:
            self._hash = hashlib.sha256(self.change_json_bytes).digest()
        return self._hash

    @property
    def encnumbasis(self) -> str:
        return base58.b58encode(b'\x12\x20' + self.hash).decode('ascii')

    @property
    def change(self) -> str:
        return self._change

    @property
    def by(self) -> List:
        return self._by

    @property
    def when(self) -> str:
        return self._when

    @property
    def change_json_bytes(self) -> bytes:
        return base64.urlsafe_b64decode(self._change)

    @property
    def change_json_str(self) -> str:
        return self.change_json_bytes.decode('utf-8')

    @property
    def change_json_dict(self) -> dict:
        return json.loads(self.change_json_bytes)

    @classmethod
    def from_dict(cls, src: dict):
        return Delta(src.get("change"), src.get("by"), src.get("when"))

    @classmethod
    def from_json(cls, json_text: Union[str, bytes]):
        return Delta.from_dict(json.loads(json_text))

    def to_dict(self):
        return {"change": self.change, "by": self._by, "when": self._when}

    def to_json(self):
        return json.dumps(self.to_dict())

    def __str__(self):
        return self.to_json()

    def __hash__(self):
        return hash(self.hash)

    def __eq__(self, other):
        if isinstance(other, Delta):
            return self.hash == other.hash
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, Delta):
            return self.hash != other.hash
        return NotImplemented
