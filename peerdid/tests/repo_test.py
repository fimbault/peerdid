import json
import os
import pytest

from ..diddoc import get_predefined, get_path_where_diddocs_differ
from ..repo import Repo
from .. import get_predefined_did_value
from ..delta import Delta
from ..file import File


def test_repo_empty_on_creation(scratch_repo):
    assert not os.listdir(scratch_repo.path)


def test_repo_creates_3_files(scratch_repo):
    scratch_repo.new_doc(get_predefined('1'))
    scratch_repo.new_doc(get_predefined('2'))
    scratch_repo.new_doc(get_predefined('3'))
    assert len(os.listdir(scratch_repo.path)) == 3


def test_repo_resolves_created_doc(scratch_repo):
    doc_1 = get_predefined('1')
    scratch_repo.new_doc(doc_1)
    # This is a bogus resolution in some ways; the doc had an "id" property but shouldn't have.
    assert scratch_repo.resolve('did:peer:1z1111111111111111111111111111111111111111111111') == \
        doc_1


def test_repo_resolves_correctly(scratch_repo):
    doc_1 = json.loads(get_predefined('1'))
    del doc_1['id']
    did = scratch_repo.new_doc(doc_1)
    resolved = scratch_repo.resolve(did)
    assert get_path_where_diddocs_differ(resolved, doc_1) == '.{id}'
    del resolved['id']
    assert get_path_where_diddocs_differ(resolved, doc_1) is None


def test_nonexistent_repo_can_be_created_mkdir_on_write_when_parent_present(scratch_space):
    r = Repo(os.path.join(scratch_space.name, 'doesnt_exist'))
    r.new_doc(get_predefined('1'))


def test_nonexistent_repo_can_be_created_complains_on_write_when_parent_missing(scratch_space):
    r = Repo(os.path.join(scratch_space.name, 'doesnt_exist/subdir'))
    with pytest.raises(FileNotFoundError):
        r.new_doc(get_predefined('1'))

def test_get_state_for_unknown_did(scratch_repo):
    with pytest.raises(AttributeError):
        scratch_repo.get_state("did:peer:foo")


def test_get_state_for_reserved_did(scratch_repo):
    with pytest.raises(AttributeError):
        scratch_repo.get_state(get_predefined_did_value('1'))


def test_get_state_for_1_normal_did(sample_delta, scratch_file, scratch_repo):
    scratch_file.append(sample_delta)
    scratch_repo.new_doc(scratch_file.genesis)
    snapshot = scratch_repo.get_state(scratch_file.did)
    assert len(snapshot) == 1
    assert snapshot[0]["did:peer:1zQmeiupQudTUZfotKWHhVVrtnA5Vu721Su68XZB35Kh3hTV"] == "WDuyVDIB7R1C6GhHX9lxhowEMCQkSw_QwBRtBvEFzVg="


def test_get_state_for_2_normal_dids(scratch_space, scratch_file, scratch_repo):
    scratch_file.append(Delta('{"publicKeys": {"key-1": "foo"}}', []))
    scratch_repo.new_doc(scratch_file.genesis)
    f2 = File(os.path.join(scratch_space.name, 'peerdid-file2'))
    f2.append(Delta('{"publicKeys": {"key-2": "foo"}}', []))
    scratch_repo.new_doc(f2.genesis)
    snapshot = scratch_repo.get_state(scratch_file.did, f2.did)
    assert len(snapshot) == 2
    did_a = 'did:peer:1zQmb6WrwDimrMTNJFZcBe86A96gF9D5APikmeeyhg4jwQuT'
    did_b = 'did:peer:1zQmXT4fGHZMnLfWyXnzMZR9qjpdNkq1w3EbvV95Z5aUsrme'
    a = snapshot[0] if did_a in snapshot[0] else snapshot[1]
    b = snapshot[1] if a == snapshot[0] else snapshot[0]
    assert did_a in a
    assert did_b in b
    assert a[did_a] == '4GKyAZVLGaSvb81v6RA3acWRzhV5vhzhHNzBCyri2Ek='
    assert b[did_b] == 'qWlggN0vuqzOtWEo_37lb5yHVHku5H7lFcYODMaR5-k='