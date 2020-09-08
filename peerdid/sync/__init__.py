
def get_state(repo, *dids):
    state = []
    for did in dids:
        file = repo.get_doc(did).file
        state.append({did: file.snapshot})
    return state

