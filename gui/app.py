"""Builds the launcher window from specs.py and binds it to runner.py."""

import importlib
import tkinter as tk
from tkinter import ttk

from gui import runner, specs
from gui.widgets import (Disclosure, LogPane, ParamField,
                         RadiusEstimatorField, ScaleField)

POLL_MS = 100          # how often the main thread drains the log queue


class ToolTab(ttk.Frame):
    """One notebook page: parameters, Run/Cancel, status, and a log."""

    def __init__(self, master, spec):
        super().__init__(master, padding=10)
        self.spec = spec
        self.fields = {}
        self.run = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        if spec.get('blurb'):
            ttk.Label(self, text=spec['blurb'], wraplength=820,
                      foreground='gray25').grid(row=0, column=0, sticky='w',
                                                pady=(0, 8))

        self._build_params(row=1)
        self._build_controls(row=2)

        self.log = LogPane(self)
        self.log.grid(row=3, column=0, sticky='nsew', pady=(8, 0))

        self._check_optional_import()

    # -- construction ----------------------------------------------------

    def _build_params(self, row):
        params = self.spec.get('params', [])
        standard = [p for p in params if not p.get('advanced')]
        advanced = [p for p in params if p.get('advanced')]

        holder = ttk.Frame(self)
        holder.grid(row=row, column=0, sticky='ew')
        holder.columnconfigure(2, weight=1)

        for i, p in enumerate(standard):
            self.fields[p['key']] = self._make_field(holder, p, i)

        if advanced:
            disclosure = Disclosure(holder, 'Advanced')
            disclosure.grid(row=len(standard), column=0, columnspan=4,
                            sticky='ew', pady=(6, 0))
            body = disclosure.body
            body.columnconfigure(2, weight=1)
            ttk.Label(body, text='⚠  ' + specs.ADVANCED_WARNING, wraplength=700,
                      foreground='#8a5a00').grid(row=0, column=0, columnspan=4,
                                                 sticky='w', pady=(0, 6))
            for i, p in enumerate(advanced, start=1):
                self.fields[p['key']] = self._make_field(body, p, i)

    def _make_field(self, master, param, row):
        kind = param.get('kind')
        if kind == 'scale':
            return ScaleField(master, param, row)
        if kind == 'estimator':
            return RadiusEstimatorField(master, param, row)
        return ParamField(master, param, row)

    def _build_controls(self, row):
        bar = ttk.Frame(self)
        bar.grid(row=row, column=0, sticky='ew', pady=(10, 0))

        self.run_button = ttk.Button(bar, text='Run', width=12, command=self.start)
        self.run_button.pack(side='left')

        self.cancel_button = ttk.Button(bar, text='Cancel', width=12,
                                        command=self.cancel, state='disabled')
        self.cancel_button.pack(side='left', padx=(6, 0))

        ttk.Button(bar, text='Clear log', width=12,
                   command=self.log_clear).pack(side='left', padx=(6, 0))

        self.progress = ttk.Progressbar(bar, mode='indeterminate', length=140)
        self.progress.pack(side='left', padx=(12, 0))

        self.status = ttk.Label(bar, text='Idle')
        self.status.pack(side='left', padx=(10, 0))

    def _check_optional_import(self):
        """Disable the tab up front when an optional dependency is absent."""
        module = self.spec.get('optional_import')
        if not module:
            return
        try:
            importlib.import_module(module)
        except ImportError:
            self.run_button.configure(state='disabled')
            self.status.configure(text=f'{module} not installed')
            self.log.append([
                f'This tool needs the optional dependency "{module}", which is '
                f'not installed.',
                '',
                'Install it with:',
                '    pip install -r requirements-optional.txt',
            ])

    def log_clear(self):
        self.log.clear()

    # -- running ---------------------------------------------------------

    def _collect(self):
        """Gather parameter values; returns dict or None after logging errors."""
        values = {}
        errors = []
        for key, field in self.fields.items():
            try:
                values[key] = field.value()
            except ValueError as exc:
                errors.append(str(exc))
        if errors:
            self.log.append(['Cannot run — fix these first:'] +
                            [f'  - {e}' for e in errors])
            self.status.configure(text='✗ Invalid input')
            return None
        return values

    def _requirements(self, values):
        fn = self.spec.get('requirements_fn')
        if fn is not None:
            return fn(values)
        return self.spec.get('requirements', [])

    def start(self):
        if self.run is not None and self.run.is_alive():
            return

        values = self._collect()
        if values is None:
            return

        problems = runner.check_requirements(self._requirements(values))
        if problems:
            self.log.append(['Cannot run — required input is missing:', ''] +
                            [f'  {p}' for p in problems])
            self.status.configure(text='✗ Missing input')
            return

        # Blank optional paths were collected as None so the callee applies its
        # own default; drop them rather than passing None explicitly.
        kwargs = {}
        for key, val in values.items():
            spec = next(p for p in self.spec['params'] if p['key'] == key)
            if val is None and not spec.get('empty_is_none') and spec.get('kind') != 'scale':
                continue
            kwargs[key] = val

        self.log.append(['', '=' * 70,
                         f'Running {self.spec["name"]}...',
                         '=' * 70])
        self._set_running(True)

        self.run = runner.Run(self.spec['target'], kwargs)

        if self.spec.get('main_thread'):
            # pyvista / matplotlib 3-D need the main thread; the window will be
            # unresponsive until their window closes.
            self.status.configure(text='Running (window may not respond)...')
            self.update_idletasks()
            self.run.run_on_this_thread()
            self._drain()
            self._finish()
        else:
            self.run.start()
            self.after(POLL_MS, self._poll)

    def cancel(self):
        if self.run is not None and self.run.is_alive():
            self.run.cancel()
            self.status.configure(text='Cancelling...')
            self.cancel_button.configure(state='disabled')

    def _poll(self):
        self._drain()
        if self.run.is_alive():
            self.after(POLL_MS, self._poll)
        else:
            self._drain()          # catch anything queued after the last poll
            self._finish()

    def _drain(self):
        lines = self.run.drain()
        if lines:
            self.log.append(lines)

    def _finish(self):
        state = self.run.status()
        labels = {'done': '✓ Done', 'failed': '✗ Failed', 'cancelled': '■ Cancelled'}
        self.status.configure(text=labels.get(state, 'Idle'))

        # formulas_printer returns its text rather than only printing it
        if state == 'done' and isinstance(self.run.result, str) and self.run.result.strip():
            self.log.append(self.run.result.rstrip().splitlines())

        self._set_running(False)

    def _set_running(self, running):
        self.run_button.configure(state='disabled' if running else 'normal')
        cancellable = running and not self.spec.get('main_thread')
        self.cancel_button.configure(state='normal' if cancellable else 'disabled')
        if running:
            self.progress.start(12)
            self.status.configure(text='Running...')
        else:
            self.progress.stop()


class LauncherApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=8)
        self.pack(fill='both', expand=True)

        notebook = ttk.Notebook(self)
        notebook.pack(fill='both', expand=True)
        self.tabs = []
        for spec in specs.TABS:
            tab = ToolTab(notebook, spec)
            notebook.add(tab, text=spec['name'])
            self.tabs.append(tab)

        master.protocol('WM_DELETE_WINDOW', self._on_close)
        self._master = master

    def _on_close(self):
        """Warn before closing while work is still running."""
        busy = [t.spec['name'] for t in self.tabs
                if t.run is not None and t.run.is_alive()]
        if busy:
            from tkinter import messagebox
            if not messagebox.askokcancel(
                    'Run in progress',
                    f'Still running: {", ".join(busy)}.\n\n'
                    'Quitting now stops it and may leave partial output. Quit anyway?'):
                return
            for t in self.tabs:
                if t.run is not None and t.run.is_alive():
                    t.run.cancel()
        self._master.destroy()


def main():
    root = tk.Tk()
    root.title('Blast Analysis Launcher')
    root.geometry('960x720')
    root.minsize(760, 560)
    LauncherApp(root)
    root.mainloop()
