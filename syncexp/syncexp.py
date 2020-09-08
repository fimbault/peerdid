import json
from jwcrypto import jwk
import os
import re
import shutil
import sys
import textwrap
import time
import traceback
import types

from agent import Agent, conn_pat
import console
import cmdlog


agent_cmd_pat = re.compile(r'\s*([a-z]\.[1-9])\s*:\s*(.+)', re.I)
should_autogossip = False


def quit():
    """\
    quit                  -- end program
    """
    sys.exit(0)


def autogossip(*args):
    """\
    autogossip on|off     -- generate random background conversation
    """
    mode = 'on' if (args and args[0].lower() == 'on') else 'off'
    stdout.say('Turning autogossip %s.' % mode)
    global should_autogossip
    should_autogossip = bool(mode == 'on')


def check(*args):
    """\
    check                 -- see whether all agents have synchronized state
    """
    agents_by_state = {}
    with Agent.all_lock:
        for a in Agent.all:
            this_state = a.state_summary
            if this_state not in agents_by_state:
                agents_by_state[this_state] = [a]
            else:
                agents_by_state[this_state].append(a)
    if len(agents_by_state) == 1:
        stdout.say('All agents agree that state is %s.' % this_state)
    else:
        report = 'Agents are not fully synchronized.'
        for key, agents in agents_by_state.items():
            report += '\n   %d agents see state as: %s  (%s)' % (len(agents), key, ', '.join([a.id for a in agents]))
        stdout.say(report)


def reach(*args):
    """\
    reach [agentpat]      -- show where specified agent(s) can reach (wildcards ok).
    """
    pat = args[0] if args else '*'
    pat = re.compile(pat.replace('.', r'[.]').replace('*', '.*').replace('?', '.'), re.I)
    summary = []
    with Agent.all_lock:
        for a in Agent.all:
            if pat.match(a.id):
                summary.append(a.id + ': ' + ', '.join(a.can_reach))
    stdout.say_pre('\n'.join(summary))


def help(*args):
    stdout.say('\nGeneral Commands')
    for item in funcs:
        if item != 'help':
            stdout.say('    ' + textwrap.dedent(globals()[item].__doc__.rstrip()))
    stdout.say("\nAgent-specific Commands")
    for item in Agent.commands:
        stdout.say('    ' + textwrap.dedent(Agent.__dict__[item].__doc__.rstrip()))
    stdout.say('')


funcs = [x for x in globals().keys() if type(globals()[x]) == types.FunctionType]


stdout = console.Console()

            
def abort(msg):
    stdout.say('Error: ' + msg)
    sys.exit(1)


def thread_main(agent):
    global should_autogossip
    try:
        while True:
            time.sleep(0.33)
            with Agent.cmds_lock:
                n = len(Agent.cmds)
            while agent.cmd_idx < n:
                agent.next()
            if should_autogossip:
                agent.autogossip()
    except:
        agent.say(traceback.format_exc())
        os._exit(1)


def expand_diddoc_template(ch, template):
    # Input validation...
    if not 'authorization' in template:
        raise Exception('Template must have "authorization" section.')
    if not 'profiles' in template['authorization']:
        raise Exception('Template must define one or more keys in  "authorization"."profiles" section.')
    # Generate public and private keys. Insert the public keys into the
    # genesis template, and build a list of private keys to correspond.
    keys = template['authorization']['profiles']
    publicKeys = []
    privateKeys = []
    n = 1
    for k in keys:
        kid = ch + '.' + str(n)
        n += 1
        k = jwk.JWK.generate(kty='EC', crv='P-256')
        decl = json.loads(k.export_private())
        decl['kid'] = kid
        privateKeys.append(decl)
        decl = json.loads(k.export_public())
        decl['kid'] = kid
        publicKeys.append(decl)
    template['publicKeys'] = publicKeys
    return privateKeys


def load_agents(session_folder, diddocs, connections):
    if len(diddocs) < 2:
        abort('Must have at least 2 parties.')
    Agent.thread_main = thread_main
    Agent.stdout = stdout
    gs = []
    privkeys = {}
    # Generate keys and build all the genesis DID docs.
    for ch, template in diddocs.items():
        privkeys[ch] = expand_diddoc_template(ch, template)
        genesis = json.dumps(template, indent=2)
        gs.append(genesis)
    # Now construct agents for each key in each DID doc.
    for ch, items in privkeys.items():
        for key in items:
            # Give each agent a place to run, its own private key, all genesis DID docs, and
            # connection info. This initializes state in the same way as doing the DID exchange
            # protocol. Since this explorer is about updating, not connecting, it's the right
            # condition to start from.
            Agent(session_folder, key, gs, connections)


def get_next_command():
    stdout.prompt()
    x = input().strip()
    with stdout:
        stdout.prompting = False
    return x


def dispatch(cmd):
    args = re.split(r'\s+', cmd)
    cmd = args[0].replace('()', '')
    args = args[1:]
    found = False
    for f in funcs:
        if f.startswith(cmd):
            cmd = f
            found = True
    if not found:
        stdout.say('Huh? Try "help".')
    else:
        func = globals()[cmd]
        func(*args)


def main():
    try:
        while True:
            cmd = get_next_command()
            m = agent_cmd_pat.match(cmd)
            if m:
                with Agent.cmds_lock:
                    Agent.cmds.append(m.group(1).upper() + ': ' + m.group(2))
            elif ':' in cmd:
                stdout.say('No such agent.')
            else:
                dispatch(cmd)
            time.sleep(1)
    except KeyboardInterrupt:
        stdout.say('')


if __name__ == '__main__':
    default_cmdline = "default A=diddoc-a.json B=diddoc-b.json A.1+-A.3,A.4 A.1+-+A.2 A.1-+B.2 A.2+-B.1,B.3 B.2+-+A.2,B.3 B.1+-+B.3 B.1-+B.2 B.4-+B.1,B.3"
    help_pat = re.compile(r'(/|--?)([?]|h(elp)?)$', re.I)

    if len(sys.argv) > 1 and help_pat.match(sys.argv[1]):
        short_name = __file__[:__file__.find('.')]
        print('\n' + console.wrap("""%s: run the peer DID sync protocol in exploratory mode.
%s

Syntax: python %s [<session name> <DID doc template mappings> <connectivity statements>]

Example args:

    %s

You can actually try these args. If your current working directory is the folder where the tool lives,
they should work nicely. They correspond to a relationship diagrammed here: http://j.mp/36ZDrTN. If you run
without any args, these are the settings that are used.

Mappings are strings in the form <X=filepath>, where X is a letter referencing a sovereign domain / identity
subject (e.g., A and B for Alice and Bob), and where filepath references a genesis template file in DID Doc
format. You need a unique mapping (different letters, though they could use the same template) for each party
(NOT each agent) in the relationship you want to model. The template files lack a `publicKey` section to
define key values, and a `service` section to define endpoints; the tool will generate data to populate those
sections. However, they do contain an `authorization` section giving privileges to keys, so you can setup
rules and watch how those rules affect the acceptance of changes propagated by different key holders.

The tool will spin up one agent for each key defined in each party's genesis doc. This means that it treats
key identifiers and agents as synonyms. Technically this is not always true; a single agent may hold more than
one key in a relationship, or none at all. But it is a simplification that has no downside as far as
exploration is concerned.

Statements about connectivity do NOT say whether information can flow at all; rather, they say whether agents
can initiate direct conversations with one another on demand. A key held on a mobile device and a key held on
a tablet probably lack this direct connectivity, whereas they can probably both contact a key held in their
own cloud agent whenever they like. These statements are directional; an offline key can probably initiate
outbound communication on demand, but other agents probably can't update the offline state without intervention
by the identity subject. Connectivity statements are in the form <XconnY,Z>, where X, Y, and Z are agent or key
identifiers like A.1 and B.2, and conn is the +-+ (bidirectional) symbol, or -+ or +- (unidirectional arrows).
The arrow/plus points to the side where an agent might be passively updated by data that they receive from the
other side. Don't put spaces between identifiers and the connector or commas.
""" % (short_name, '-'*console.cols, __file__, default_cmdline)))
        sys.exit(0)

    diddoc_pat = re.compile(r'([A-Z])=(.*)$', re.I)

    if len(sys.argv) == 1:
        args = default_cmdline.split(' ')
    else:
        args = sys.argv[1:]
    session = args[0]
    args = args[1:]
    diddocs = {}
    connections = []
    for arg in args:
        m = diddoc_pat.match(arg)
        if m:
            c = m.group(1).upper()
            if c in diddocs:
                raise Exception("Can't specify template for %s more than once." % c)
            path = m.group(2)
            if path.startswith('"'):
                path = path[1:-1]
            with open(path, 'rt') as f:
                diddocs[c] = json.loads(re.sub('([#"])[xX][.]', r'\1' + c + '.', f.read()))
        else:
            m = conn_pat.match(arg)
            if not m:
                raise Exception("Unrecognized arg %s.")
            connections.append(arg.upper())

    session_folder = os.path.join(os.path.expanduser('~/.syncexp'), session)
    stdout.say("Running session in %s." % session_folder)
    if os.path.isdir(session_folder):
        shutil.rmtree(session_folder)
    os.makedirs(session_folder)

    load_agents(session_folder, diddocs, connections)
    main()