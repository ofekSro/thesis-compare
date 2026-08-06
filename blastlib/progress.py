"""Unicode-safe progress printing for a project living under a Hebrew path.

WHY THIS EXISTS
---------------
The repository sits below a directory whose name is Hebrew. On Windows
consoles whose codec is narrower than the message (cp1252 is the usual
default), ``print()`` of any resolved path raises UnicodeEncodeError and
kills an otherwise-finished batch run at its very last line — the line that
echoes where the output went. Every tool that prints paths hit this.

Routing user-facing prints through ``say`` keeps runs alive on any console:
characters the console cannot carry degrade to '?' instead of a traceback.

Every entry point follows the same idiom:

    def main(*, ..., progress=None):
        say = progress or blastlib.progress.say

so the GUI can substitute its own line sink (its runner also implements
cooperative cancellation by raising from the callback — which is why batch
loops must call ``say`` at least once per config), while CLI runs get the
safe printer. This function was born as ``_say`` in the retired
tools/pressure_profile/pressure_profile.py and promoted here when the street
suite made a third tool import it across tool directories.
"""

import sys


def say(msg):
    """print() that survives a console codec narrower than the message."""
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or 'ascii'
        print(msg.encode(enc, 'replace').decode(enc))
