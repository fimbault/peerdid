import copy
import json
import os
import random
import re
import threading
import time

try:
    # See if peerdid module is installed.
    from peerdid.repo import Repo
except:
    import os
    import sys
    # If not, then assume we're working with source code.
    # Resolve relative paths.
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from peerdid.repo import Repo
from peerdid import abbreviate


valid_spec = r'[A-Za-z]\.[1-9](?:@([a-z]+))?(?:-([A-Za-z]\.[1-9](?:,[A-Za-z]\.[1-9])*))?'
valid_spec_pat = re.compile(r'^%s$' % valid_spec)
m_of_n_of_group_pat = re.compile(r'^(.*?)(?: by {(.*?)}/)?([1-9])@([a-z])$')
simple_pat = re.compile(r'simple(?:\s+by\s+([1-9]@[a-z]))?$')
add_rem_pat = re.compile(r'([a-z]+)\s+(%s)(?:\s+by\s+([1-9]@[a-z]))?$' % valid_spec)
conn_pat = re.compile(r'([A-Z][.]\d)(\+-?\+|-\+|\+-)([A-Z].*)$')
kid_pat = re.compile(r'"kid"\s*:\s*"([^"]+)"')


def get_reachable(id, connections):
    reachable = []
    for conn in connections:
        i = conn.find(id)
        if i > -1:
            # Is there an arrow pointing away from this id? If so, whatever's on the
            # opposite side of the connector symbol from us is reachable by us.
            m = conn_pat.match(conn)
            if i < m.start(2) and m.group(2).endswith('+'):
                reachable += m.group(3).split(',')
            elif i >= m.end(2) and m.group(2).startswith('+'):
                reachable.append(m.group(1))
    reachable.sort()
    return reachable


def get_relationship(my_party, all_parties):
    if len(all_parties) == 2:
        other = [p for p in all_parties if p != my_party][0]
        return my_party + other
    all_parties.sort()
    return '+'.join(all_parties)


class Agent:
    """
    Represents an agent that's participating in the peer DID sync protocol.
    """
    all_lock = threading.Lock()
    all = []
    thread_main = None
    stdout = None
    cmds_lock = threading.Lock()
    cmds = []

    def __init__(self, session_folder, key, all_genesis, connections):
        self.key = key
        self.repo = Repo(os.path.join(session_folder, self.id))
        self.can_reach = get_reachable(self.id, connections)
        self.cmd_idx = 0
        self.thread = threading.Thread(target=Agent.thread_main, args=(self,), daemon=True)
        self.dids_by_party = {}
        for genesis in all_genesis:
            did = self.repo.new_doc(genesis)
            m = kid_pat.search(genesis)
            self.dids_by_party[m.group(1)[0]] = did
        self.did = self.dids_by_party[self.party]
        self.relationship = get_relationship(self.party, self.dids_by_party.keys())
        self.say("Ready to sync in the %s relationship." % self.relationship)
        with Agent.all_lock:
            Agent.all.append(self)
        self.thread.start()

    @property
    def id(self):
        return self.key['kid']

    @property
    def party(self):
        return self.id[0]

    @property
    def num(self):
        return self.id[2]

    def next(self):
        handled = True
        cmd = self.cmds[self.cmd_idx]
        if cmd.startswith(self.id):
            rest = cmd[4:].lstrip()
            m = simple_pat.match(rest)
            if m:
                self.simple(m.group(1))
            elif rest.startswith('state'):
                self.state()
            elif rest.startswith('gossip'):
                self.say('Gossipping.')
                self.gossip()
            elif rest.startswith('res'):
                self.resolve(rest[rest.find(' ') + 1:].lstrip())
            else:
                m = add_rem_pat.match(rest)
                if m:
                    if m.group(1) == 'add':
                        self.add(m.group(2), m.group(5))
                    elif m.group(1) == 'rem':
                        self.rem(m.group(2), m.group(5))
                    else:
                        handled = False
                else:
                    handled = False
        if not handled:
                self.say('Huh? Try "help".')
        self.cmd_idx += 1

    def simple(self, auth=None):
        """\
        A.2: simple [by N@M]  -- simulate a simple delta that doesn't change active agents
                                 (key rotate, add/remove rule, add/remove endpoint), optionally
                                 requiring N signatures from group M
        """
        delta = '#' + hex(random.randint(4096, 256*256))[2:]
        if auth:
            delta += ' by ' + auth
        delta = self.append_delta(delta)
        self.say('Created delta %s. I now see %s.' % (delta, self.all_deltas))
        self.broadcast(self.party + '+' + delta)

    def add(self, spec, auth=None):
        """\
        A.8: add A.9 [by N@M] -- simulate a delta that adds an active agent, optionally
                                 requiring N signatures from group M
        """
        try:
            party, num, groups, subtracted = norm_spec(spec)
        except:
            self.say('Bad spec "%s".' % spec)
            return
        if party != self.party:
            self.say("I'm in %s; I can't add a key for %s." % (self.party, party))
            return
        with Agent.all_lock:
            for a in Agent.all:
                if a.party == party and a.num == num:
                    self.say('Agent %s already exists.' % spec)
                    return

        delta = '#add-%s.%s' % (party, num)
        if auth:
            delta += ' by {}/' + auth
        delta = self.append_delta(delta)
        new_agent = Agent(spec, copy.deepcopy(self.deltas))
        self.broadcast(self.party + '+' + delta)

    def resolve(self, did):
        """\
        A.2: res A.did@AB     -- resolve the specified DID
        """
        which_did = self.dids_by_party[did[0].upper()]
        diddoc = self.repo.resolve(which_did)
        self.say_pre(json.dumps(diddoc, indent=2))

    def rem(self, spec, suffix=None):
        """\
        A.2: rem A.4 [by N@M] -- simulate a delta that removes an active agent, optionally
                                 requiring N signatures from group M
        """
        pass

    def say(self, msg):
        Agent.stdout.say(self.id + ' --\n       ' + msg)

    def say_pre(self, msg):
        # Do simple indenting
        msg = msg.replace('\n', '\n       ')
        Agent.stdout.say_pre(self.id + ' -- ' + msg)

    @property
    def all_deltas(self):
        with self.deltas_lock:
            return '; '.join([x + '=' + self.get_state(x) for x in sorted(self.deltas.keys())])

    @property
    def state_summary(self):
        items = []
        for did in self.dids_by_party.values():
            short_did = abbreviate(did)
            snapshot = self.repo.get_doc(did).file.snapshot
            short_snapshot = snapshot[:3] + '...' + snapshot[-3:]
            items.append('%s = %s' % (short_did, short_snapshot))
        items.sort()
        return '; '.join(items)

    def state(self):
        """\
        B.3: state            -- report my state
        """
        self.say_pre(self.state_summary)

    def get_state(self, party=None):
        if party is None:
            party = self.party
        return '+'.join(self.deltas[party])

    def __str__(self):
        return self.id

    def receive(self, msg):
        party = msg[0]
        self.append_delta(msg[2:], party)
        self.say('Received delta. I now see ' + self.all_deltas)
        # Introduce some randomness so order of events from other agents
        # can vary.
        time.sleep(random.random() / 8)

    def append_delta(self, delta, party=None):
        if party is None:
            party = self.party
        lst = self.deltas[party]
        with self.deltas_lock:
            # Disregard deltas that we already know about.
            if delta not in lst:
                # Is this an m-of-n change?
                match = m_of_n_of_group_pat.match(delta)
                if match:
                    # Figure out endorsers, n, and group name.
                    endorsers = match.group(2).split(',') if match.group(2) else []
                    n = int(match.group(3))
                    group = match.group(4)
                    # Do we already know about this delta, but with different
                    # endorsers?
                    old_idx = -1
                    i = 0
                    endorsers_updated = False
                    for old in lst:
                        if old.startswith(match.group(1)):
                            old_match = m_of_n_of_group_pat.match(old)
                            old_endorsers = old_match.group(2).split(',') if old_match.group(2) else []
                            new_endorsers = sorted(list(set(endorsers + old_endorsers)))
                            if new_endorsers != endorsers:
                                endorsers_updated = True
                                endorsers = new_endorsers
                            old_idx = i
                            break
                        i += 1
                    # Can we endorse this change? Or do we know something about the endorsements that this
                    # change didn't know?
                    if len(endorsers) < n and (party == self.party) and (group in self.groups) and self.id not in endorsers:
                        # A newly added agent can't endorse the txn that adds itself.
                        if not delta.startswith('add-' + self.id):
                            endorsers.append(self.id)
                            endorsers.sort()
                            endorsers_updated = True
                    if endorsers_updated:
                        delta = '%s by {%s}/%s@%s' % (match.group(1), ','.join(endorsers), n, group)
                    if old_idx > -1:
                        lst[old_idx] = delta
                    else:
                        lst.append(delta)
                else:
                    lst.append(delta)
                lst.sort()
        return delta

    def broadcast(self, delta):
        self.say('Broadcasting to agents I can reach.')
        targets = self.reachable
        if targets:
            for a in targets:
                a.receive(delta)

    def gossip(self, targets=None):
        """\
        A.1: gossip           -- talk to any agents that A.1 can reach
        """
        if targets is None:
            targets = self.reachable
        if targets:
            def sync(s, t):
                for key in s.deltas:
                    for delta in s.deltas[key]:
                        if delta not in t.deltas[key]:
                            s.say('%s+%s--> %s' % (key, delta, t.id))
                            t.receive(key + '+' + delta)
            for t in targets:
                sync(self, t)
                sync(t, self)

    def autogossip(self):
        if random.random() < 0.05:
            target = random.choice(self.reachable)
            self.gossip([target])

    commands = ['simple', 'add', 'rem', 'state', 'gossip', 'resolve']