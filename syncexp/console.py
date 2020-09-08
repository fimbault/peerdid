import os
import re
import sys
import textwrap
import threading

try:
    column_count = max(os.get_terminal_size()[0], 40)
except:
    column_count = 80

_leading_lines_pat = re.compile(r'^(\n[ \t]*)+')
_trailing_lines_pat = re.compile('(\n[ \t]*)$')
_paragraph_pat = re.compile(r'^\n[ \t]*\n')
_leading_indent_pat = re.compile(r'^[ \t]+')
_run_of_whitepace_pat = re.compile(r' {2,}')
_hanging_indent = re.compile(r' *(\n +)')
_placeholder = chr(1)


# We shouldn't have to do this, according to docs for textwrap. However, I can't
# get the textwrap *_whitespace and expand_tabs params to work the way I expect...
def _cleanup(p):
    p = p.rstrip()
    prefix = hang = ''
    m = _leading_indent_pat.match(p)
    if m:
        prefix = p[:m.end()]
        p = p[m.end():]
    m = _hanging_indent.search(p)
    if m:
        hang = m.group(1)[1:]
        p = _hanging_indent.sub(' ', p)
    return prefix + p, prefix + hang


def wrap(str, **kwargs):
    if 'width' not in kwargs:
        kwargs['width'] = column_count - 1
    kwargs['tabsize'] = 4
    wrapped = []
    for p in _paragraph_pat.split(str):
        p, hang = _cleanup(p)
        kwargs['subsequent_indent'] = hang
        wrapped.append(textwrap.fill(p, **kwargs))
    return '\n\n'.join(wrapped)


class Console:
    def __init__(self):
        self.lock = threading.Lock()
        self.prompting = False

    def __enter__(self):
        self.lock.acquire()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.lock.release()

    def prompt(self):
        with self:
            sys.stdout.write('> ')
            self.prompting = True

    def say_pre(self, msg):
        with self:
            if self.prompting:
                sys.stdout.write('\n')
                self.prompting = False
            if msg:
                sys.stdout.write(msg)
            sys.stdout.write('\n')

    def say(self, msg):
        with self:
            if self.prompting:
                sys.stdout.write('\n')
                self.prompting = False
            if msg:
                kwargs = {}
                # Do some specialized handling of blank lines at front of str.
                prefix = _leading_lines_pat.match(msg)
                if prefix:
                    # Write as many blank lines as we were given.
                    sys.stdout.write('\n' * prefix.group(1).count('\n'))
                    # Figure out indent from first non-blank line.
                    i = prefix.end() - 1
                    n = 0
                    while msg[i] != '\n':
                        n = n + (1 if msg[i] == ' ' else 4)
                        i -= 1
                    msg = msg[prefix.end():]
                    kwargs['initial_indent'] = kwargs['subsequent_indent'] = ' ' * n
                suffix = _trailing_lines_pat.search(msg)
                if suffix:
                    rest = '\n' * msg[suffix.start()].count('\n')
                    msg = msg[:suffix.start()]
                    suffix = rest
                msg = wrap(msg, **kwargs)
                sys.stdout.write(msg)
                if suffix:
                    sys.stdout.write(suffix)
            sys.stdout.write('\n')
