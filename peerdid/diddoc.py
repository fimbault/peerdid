import json
import os
import re
from typing import Union

from .file import File, canonical_fname
from .jsondetect import str_seems_like_json, bytes_seems_like_json


class DIDDoc:
    def __init__(self, path_or_File: Union[str, File]):
        if isinstance(path_or_File, File):
            self._file = path_or_File
            self._folder = None
        else:
            if os.path.isdir(path_or_File):
                self._folder = os.path.normpath(path_or_File)
                self._file = None
            elif os.path.isfile(path_or_File):
                self._file = File(path_or_File)
                self._folder = None
            else:
                raise ValueError("Can't tell whether a path that doesn't exist is file or folder.")

    @property
    def did(self) -> str:
        if self._file:
            return self._file.did

    def append(self, delta):
        if not self._file:
            self._file = File(os.path.join(self._folder, canonical_fname(delta.encnumbasis)))
        self._file.append(delta)

    @property
    def file(self):
        return self._file

    @property
    def path(self):
        f = self.file
        if f:
            return f.path

    def apply_delta(self, json_dict, delta):
        change_fragment = delta.change_json_dict

        def add_to_list(list_name, container):
            d = container.get(list_name)
            if d:
                items = json_dict.get(list_name)
                if not items:
                    items = json_dict[list_name] = []
                items.append(d[0])
                return d[0]

        def find_item_by_id(list, id):
            if list:
                for item in list:
                    if item.id == id:
                        return list, item

        deleted_id = add_to_list('deleted', change_fragment)
        if deleted_id:
            list, found = find_item_by_id(json_dict.get('publicKey'), deleted_id)
            if found:
                list.remove(found)
            json_dict.get('authentication', []).remove(deleted_id)
            list, found = find_item_by_id(json_dict.get('authorization', {}).get('profiles'), deleted_id)
            if found:
                list.remove(found)
        if add_to_list('publicKey', change_fragment):
            add_to_list('authentication', change_fragment)
            add_to_list('profiles', change_fragment.get('authorization', []))
        add_to_list('rules', change_fragment)

    def resolve(self, as_of:str = None) -> dict:
        f = self.file
        if not f:
            return
        g = f.genesis
        if not g:
            return
        json_dict = g.change_json_dict
        for item in self.file.deltas[1:]:
            if as_of and (item.when > as_of):
                break
            self.apply_delta(json_dict, item)
        json_dict['id'] = self.did
        return json_dict

    @property
    def did(self) -> str:
        f = self.file
        if f:
            return f.did


_predefined_diddoc_template = """\
{
    "@context": "https://w3id.org/did/v1",
    "id": "did:peer:1z%s",
    "service": [{
        "type": "did-communication",
        "serviceEndpoint": "https://localhost:12345"
    }],
    "publicKey": [
        {
            "id": "key-1",
            "type": "Ed25519VerificationKey2018",
            "publicKeyBase58": "GBMBzuhw7XgSdbNffh8HpoKWEdEN6hU2Q5WqL1KQTG5Z"
        },
        {
            "id": "key-3",
            "type": "Secp256k1VerificationKey2018",
            "controller": "#id",
            "publicKeyHex": "3056301006072a8648ce3d020106052b8104000a03420004a34521c8191d625ff811c82a24a60ff9f174c8b17a7550c11bba35dbf97f3f04392e6a9c6353fd07987e016122157bf56c487865036722e4a978bb6cd8843fa8"
        },
        {
            "id": "key-5",
            "type": "RsaVerificationKey2018",
            "controller": "#id",
            "publicKeyPem": "-----BEGIN PUBLIC KEY-----\\r\\nMIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAoZp7md4nkmmFvkoHhQMw\\r\\nN0lcpYeKfeinKir7zYWFLmpClZHawZKLkB52+nnY4w9ZlKhc4Yosrw/N0h1sZlVZ\\r\\nfOQBnzFUQCea6uK/4BKHPhiHpN73uOwu5TAY4BHS7fsXRLPgQFB6o6iy127o2Jfb\\r\\nUVpbNU/rJGxVI2K1BIzkfrXAJ0pkjkdP7OFE6yRLU4ZcATWSIPwGvlF6a0/QPC3B\\r\\nbTvp2+DYPDC4pKWxNF/qOwOnMWqxGq6ookn12N/GufA/Ugv3BTVoy7I7Q9SXty4u\\r\\nUat19OBJVIqBOMgXsyDz0x/C6lhBR2uQ1K06XRa8N4hbfcgkSs+yNBkLfBl7N80Q\\r\\n0Wkq2PHetzQU12dPnz64vvr6s0rpYIo20VtLzhYA8ZxseGc3s7zmY5QWYx3ek7Vu\\r\\nwPv9QQzcmtIQQsUbekPoLnKLt6wJhPIGEr4tPXy8bmbaThRMx4tjyEQYy6d+uD0h\\r\\nXTLSjZ1SccMRqLxoPtTWVNXKY1E84EcS/QkqlY4AthLFBL6r+lnm+DlNaG8LMwCm\\r\\ncz5NMag9ooM9IqgdDYhUpWYDSdOvDubtz1YZ4hjQhaofdC2AkPXRiQvMy/Nx9WjQ\\r\\nn4z387kz5PK5YbadoZYkwtFttmxJ/EQkkhGEDTXoSRTufv+qjXDsmhEsdaNkvcDP\\r\\n1uiCSY19UWe5LQhIMbR0u/0CAwEAAQ==\\r\\n-----END PUBLIC KEY-----"
        }
    ],
    "authentication": ["#key-1", "#key-3", "#key-5"]
}
"""


def get_predefined(which) -> str:
    which = which[0].lower()
    if which in '12345d':
        return _predefined_diddoc_template % (which*45)
    elif which == 'c':
        return 'invalid DID doc'
    elif which == 'e':
        return """{
    "@context": "https://w3id.org/did/v0.11",
    "service": [],
    "publicKey": [],
    "authentication": []
}
"""


class ValidationError(BaseException):
    def __init__(self, msg):
        BaseException.__init__(self, msg)



def _require(dict, key, value_type, contained_type=None, allow_empty=False, regex=None, allow_missing=False):
    class Missing: pass
    missing = Missing()
    value = dict.get(key, missing)
    if value is missing:
        if not allow_missing:
            raise ValidationError('Missing "%s" property' % key)
    else:
        if not isinstance(value, value_type):
            raise ValidationError('Property "%s" is of wrong type. Expected %s, not %s.' % (
                key, type(value).__name__, value_type.__name__))
        if contained_type:
            if len(x) == 0:
                if not allow_empty:
                    raise ValidationError('Property "%s" cannot be empty.' % key)
            else:
                i = 0
                for item in value:
                    if not isinstance(item, contained_type):
                        raise ValidationError('Item %s[%d] is of wrong type. Expected %s, not %s.' % (
                            key, i, contained_type.__name__, type(item).__name__
                        ))
                    i += 1
                if regex:
                    i = 0
                    for item in value:
                        if not regex.match(item):
                            raise ValidationError('Item %s[%d] doesn\'t match regex "%s".' % (
                                key, i, regex.pattern
                            ))
                        i += 1
        elif regex:
            if not regex.match(value):
                raise ValidationError('Property "%s" doesn\'t match regex "%s".' % (
                    key, regex.pattern
                ))


def validate(did_doc):
    json_dict = None
    if isinstance(did_doc, bytes):
        json_text = did_doc.decode("utf-8")
    elif isinstance(did_doc, str):
        pass
    elif isinstance(did_doc, dict):
        json_dict = did_doc
    else:
        raise ValidationError('Bad datatype. Expected bytes, string, or JSON dict, not %s.' % did_doc.__class__.__name__)
    if not json_dict:
        json_dict = json.loads(did_doc)
    _require(json_dict, '@context', str, regex=re.compile(r'https://w3id.org/did/v1'))


def _get_object_subset(set_a, set_b):
    matched = []
    i = 0
    for a_item in set_a:
        found = False
        for b_item in set_b:
            if b_item not in matched:
                path = _get_path_where_jsonld_objects_differ(a_item, b_item, '')
                if not path:
                    matched.append(b_item)
                    found = True
                    break
        if not found:
            return i, None
    return None, matched


def _get_path_where_jsonld_sets_differ(a_value, b_value, path):
    if not a_value:
        if not b_value:
            return None
        return path
    set_of_objects = bool(isinstance(a_value[0], dict))
    if set_of_objects:
        gap_idx, matches_in_b = _get_object_subset(a_value, b_value)
        if gap_idx is not None:
            return path + '[%d]' % gap_idx
        # a_value is a subset of b. Prove that b is also a subset of a.
        # Normally this should be trivial (make sure the lists are the same
        # length) -- but it's possible for one list to contain the same item
        # more than once. Since JSON-LD defines sequences as sets, not lists,
        # comparison has to be a bit more careful.
        if len(matches_in_b) < len(b_value):
            remainder = [b_item for b_item in b_value if b_item not in matches_in_b]
            gap_idx, matches_in_a = _get_object_subset(remainder, a_value)
            if not matches_in_a:
                return path
        return None
    else:
        set_of_sets = bool(isinstance(a_value[0], list))
        if set_of_sets:
            raise NotImplemented
        else:
            if set(a_value) != set(b_value):
                return path


def _get_path_where_jsonld_objects_differ(a, b, path):
    a_keys = set(a.keys())
    b_keys = set(b.keys())
    if a_keys != b_keys:
        missing = {a for a in a_keys if a not in b_keys}
        missing = missing.union({b for b in b_keys if b not in a_keys})
        return path + '.{' + ','.join(missing) + '}'
    for key, a_value in a.items():
        subpath = path + '.' + key
        a_type = type(a_value)
        b_value = b.get(key)
        if type(b_value) != a_type:
            return subpath
        if a_type is list:
            diff_path = _get_path_where_jsonld_sets_differ(a_value, b_value, subpath)
            if diff_path:
                return diff_path
        elif a_type is dict:
            diff_path = _get_path_where_jsonld_objects_differ(a_value, b_value)
            if diff_path:
                return diff_path
        else:
            if a_value != b_value:
                return subpath


def as_dict(did_doc):
    if isinstance(did_doc, dict):
        return did_doc
    elif isinstance(did_doc, str):
        if str_seems_like_json(did_doc):
            return json.loads(did_doc)
    elif isinstance(did_doc, bytes):
        if bytes_seems_like_json(did_doc):
            return json.loads(did_doc)
    raise ValueError("DID doc isn't JSON.")


def get_path_where_diddocs_differ(did_doc_1, did_doc_2):
    did_doc_1 = as_dict(did_doc_1)
    did_doc_2 = as_dict(did_doc_2)
    return _get_path_where_jsonld_objects_differ(did_doc_1, did_doc_2, '')