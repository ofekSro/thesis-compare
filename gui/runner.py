"""Background execution for the GUI launcher.

No tkinter imports live here — this module knows nothing about widgets. It
runs a target callable on a worker thread, forwards its ``progress`` lines
through a queue, and supports cooperative cancellation.

Cancellation note: the pipeline functions expose no cancel parameter, and the
launcher must not modify them. Instead the ``progress`` callback we hand them
raises :class:`RunCancelled` once the cancel flag is set. Every long loop in
the pipeline emits a progress line per config/iteration, so the exception
unwinds at the next one. A run stopped this way may have written only part of
its outputs — the log says so explicitly.
"""

import queue
import threading
import traceback
from pathlib import Path


class RunCancelled(Exception):
    """Raised inside the worker thread to unwind a cancelled run."""


class MissingInputs(Exception):
    """Raised by preflight when required files/directories are absent."""

    def __init__(self, problems):
        super().__init__('; '.join(problems))
        self.problems = problems


def check_requirements(requirements):
    """Validate a list of requirement descriptors before running.

    Each requirement is a dict:
        {'path': Path, 'kind': 'file'|'dir'|'glob', 'label': str,
         'pattern': str (glob only), 'hint': str}

    Returns a list of human-readable problem strings (empty when all satisfied).
    """
    problems = []
    for req in requirements:
        path = Path(req['path'])
        kind = req.get('kind', 'file')
        label = req.get('label', str(path))
        hint = req.get('hint', '')

        if kind == 'file':
            ok = path.is_file()
        elif kind == 'dir':
            ok = path.is_dir()
        elif kind == 'glob':
            ok = path.is_dir() and any(path.glob(req.get('pattern', '*')))
        else:
            raise ValueError(f'unknown requirement kind: {kind!r}')

        if not ok:
            msg = f'Missing {label}: {path}'
            if hint:
                msg += f'\n    -> {hint}'
            problems.append(msg)
    return problems


class Run:
    """One in-flight (or finished) execution of a tool.

    The GUI polls :meth:`drain` on the main thread to collect log lines, and
    :meth:`is_alive` to know when to re-enable its Run button.
    """

    def __init__(self, target, kwargs, on_done=None):
        self._target = target
        self._kwargs = dict(kwargs)
        self._on_done = on_done
        self._queue = queue.Queue()
        self._cancel = threading.Event()
        self._thread = None
        self.result = None
        self.error = None
        self.cancelled = False
        self.finished = False

    # -- worker side -----------------------------------------------------

    def _emit(self, *args):
        """The ``progress`` callback handed to the pipeline function."""
        if self._cancel.is_set():
            raise RunCancelled()
        text = ' '.join(str(a) for a in args) if args else ''
        self._queue.put(text)

    def _work(self):
        try:
            self.result = self._target(progress=self._emit, **self._kwargs)
        except RunCancelled:
            self.cancelled = True
            self._queue.put('')
            self._queue.put('*** CANCELLED — outputs for this run may be incomplete. ***')
        except Exception as exc:                      # surfaced, never silent
            self.error = exc
            self._queue.put('')
            self._queue.put('*** ERROR ***')
            self._queue.put(traceback.format_exc().rstrip())
        finally:
            self.finished = True
            if self._on_done is not None:
                self._on_done(self)

    # -- GUI side --------------------------------------------------------

    def start(self):
        """Run on a daemon worker thread."""
        self._thread = threading.Thread(target=self._work, daemon=True)
        self._thread.start()
        return self

    def run_on_this_thread(self):
        """Run synchronously — for tools whose GUI toolkit needs the main thread."""
        self._work()
        return self

    def cancel(self):
        """Request cancellation; takes effect at the next progress line."""
        self._cancel.set()

    def cancel_requested(self):
        return self._cancel.is_set()

    def is_alive(self):
        return self._thread is not None and self._thread.is_alive()

    def drain(self, limit=500):
        """Return up to *limit* pending log lines without blocking."""
        lines = []
        for _ in range(limit):
            try:
                lines.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return lines

    def status(self):
        """Terminal state as a short label, or None while still running."""
        if not self.finished:
            return None
        if self.cancelled:
            return 'cancelled'
        if self.error is not None:
            return 'failed'
        return 'done'
