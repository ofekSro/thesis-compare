"""Live figure tab: redraw on every change, write a file only on request.

Every other tab in this launcher is run-and-log — press Run, a worker thread
calls a pipeline function, output scrolls past. That shape does not fit a plot
you want to steer: you would save a PNG, open it, adjust, save again.

This tab embeds a matplotlib canvas instead. Changing any widget redraws
immediately into the SAME Figure object (config_curve.main draws into a
supplied fig and returns it rather than writing), and nothing reaches disk
until Save figure is pressed.

Drawing happens on the main thread. It is fast enough — a redraw with all 95
context curves is well under the threshold where a spinner would be warranted —
and matplotlib is not thread-safe, so a worker would need its own Agg figure
and a blit back. Not worth it for the latency involved.
"""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_TOOL_DIR = str(PROJECT_ROOT / 'tools' / 'config_curve')
if _TOOL_DIR not in sys.path:
    sys.path.append(_TOOL_DIR)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from matplotlib.backends.backend_tkagg import (  # noqa: E402
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure  # noqa: E402

from blastlib import constants, paths  # noqa: E402
from blastlib.processing.radius_estimator import (  # noqa: E402
    VALID_METHODS, resolve_estimator)
from gui.specs import available_radius_methods  # noqa: E402


class ConfigCurveTab(ttk.Frame):
    """Controls on the left, live figure on the right."""

    def __init__(self, master, spec):
        super().__init__(master, padding=8)
        self.spec = spec
        self._configs = []
        self._filter_vars = {}
        self._dirty = False        # something changed since the last redraw
        self._last_error = None

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_controls()
        self._build_canvas()
        self._sync_filter_states()      # range boxes start disabled

        self.after(50, self._first_draw)

    # -- construction ----------------------------------------------------

    def _build_controls(self):
        side = ttk.Frame(self)
        side.grid(row=0, column=0, sticky='nsw', padx=(0, 10))

        row = 0
        if self.spec.get('blurb'):
            ttk.Label(side, text=self.spec['blurb'], wraplength=250,
                      foreground='gray25').grid(row=row, column=0, columnspan=2,
                                                sticky='w', pady=(0, 8))
            row += 1

        ttk.Label(side, text='Config:').grid(row=row, column=0, sticky='w')
        self.config_var = tk.StringVar()
        self.config_box = ttk.Combobox(side, textvariable=self.config_var,
                                       width=30, state='readonly')
        self.config_box.grid(row=row, column=1, sticky='ew', pady=2)
        self.config_box.bind('<<ComboboxSelected>>', self._changed)
        row += 1

        ttk.Label(side, text='Target:').grid(row=row, column=0, sticky='w')
        self.target_var = tk.StringVar(value='pressure')
        box = ttk.Combobox(side, textvariable=self.target_var, width=30,
                           state='readonly', values=['pressure', 'impulse'])
        box.grid(row=row, column=1, sticky='ew', pady=2)
        box.bind('<<ComboboxSelected>>', self._changed)
        row += 1

        ttk.Label(side, text='X axis:').grid(row=row, column=0, sticky='w')
        self.x_var = tk.StringVar(value='Z')
        xbar = ttk.Frame(side)
        xbar.grid(row=row, column=1, sticky='w', pady=2)
        for val, text in (('Z', 'Z (scaled)'), ('R', 'R (metres)')):
            ttk.Radiobutton(xbar, text=text, value=val, variable=self.x_var,
                            command=self._changed).pack(side='left', padx=(0, 8))
        row += 1

        ttk.Label(side, text='Estimator:').grid(row=row, column=0, sticky='w')
        self.method_var = tk.StringVar(
            value=constants.RADIUS_ESTIMATOR['method'])
        mbox = ttk.Combobox(side, textvariable=self.method_var, width=30,
                            state='readonly',
                            values=available_radius_methods())
        mbox.grid(row=row, column=1, sticky='ew', pady=2)
        # rescan tokens whenever the list drops down, so a soft run finished
        # in the Analysis tab appears here without restarting the launcher
        mbox.configure(postcommand=lambda:
                       mbox.configure(values=available_radius_methods()))
        mbox.bind('<<ComboboxSelected>>', self._reload_configs)
        row += 1

        # -- context group
        group = ttk.LabelFrame(side, text='Background configs', padding=6)
        group.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        row += 1

        self.context_on = tk.BooleanVar(value=False)
        ttk.Checkbutton(group, text='Show other configs',
                        variable=self.context_on,
                        command=self._changed).grid(row=0, column=0, columnspan=2,
                                                    sticky='w')

        ttk.Label(group, text='Restrict to configs by:',
                  foreground='gray25').grid(row=1, column=0, columnspan=4,
                                            sticky='w', pady=(6, 2))

        # column headers for the range entries
        ttk.Label(group, text='same', foreground='gray').grid(
            row=2, column=1, sticky='w')
        ttk.Label(group, text='from', foreground='gray').grid(
            row=2, column=2, sticky='w')
        ttk.Label(group, text='to', foreground='gray').grid(
            row=2, column=3, sticky='w')

        import config_curve
        self._filters_spec = config_curve.CONTEXT_FILTERS
        for i, (key, meta) in enumerate(self._filters_spec.items(), start=3):
            self._filter_vars[key] = self._make_filter_row(group, key, meta, i)

        ttk.Label(group,
                  text='Tick a property, then either leave "same" ticked or '
                       'type a from/to range.',
                  foreground='gray', wraplength=280).grid(
                      row=98, column=0, columnspan=4, sticky='w', pady=(6, 0))

        self.context_count = ttk.Label(group, text='', foreground='gray',
                                       wraplength=280)
        self.context_count.grid(row=99, column=0, columnspan=4, sticky='w',
                                pady=(4, 0))
        row += 1

        # -- actions
        bar = ttk.Frame(side)
        bar.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(12, 0))
        ttk.Button(bar, text='Save figure', width=14,
                   command=self.save).pack(side='left')
        ttk.Button(bar, text='Redraw', width=10,
                   command=self.redraw).pack(side='left', padx=(6, 0))
        row += 1

        self.status = ttk.Label(side, text='', wraplength=250)
        self.status.grid(row=row, column=0, columnspan=2, sticky='w', pady=(8, 0))

        side.columnconfigure(1, weight=1)

    def _make_filter_row(self, group, key, meta, row):
        """One property: enable checkbox, 'same' toggle, and from/to entries.

        Returns the dict of vars/widgets the value reader needs. Ticking
        'same' greys the range boxes out, so the two modes can never both be
        half-specified.
        """
        on = tk.BooleanVar(value=False)
        same = tk.BooleanVar(value=True)
        lo = tk.StringVar()
        hi = tk.StringVar()

        # the label already reads "same charge weight" etc.
        ttk.Checkbutton(group, text=meta['label'].replace('same ', ''),
                        variable=on, command=self._filter_toggled).grid(
                            row=row, column=0, sticky='w')
        same_box = ttk.Checkbutton(group, variable=same,
                                   command=self._filter_toggled)
        same_box.grid(row=row, column=1, sticky='w')

        lo_entry = ttk.Entry(group, textvariable=lo, width=6)
        hi_entry = ttk.Entry(group, textvariable=hi, width=6)
        lo_entry.grid(row=row, column=2, sticky='w', padx=(2, 2))
        hi_entry.grid(row=row, column=3, sticky='w')

        # typing a bound redraws, but only once the user pauses
        for var in (lo, hi):
            var.trace_add('write', lambda *_: self._changed())

        return dict(on=on, same=same, lo=lo, hi=hi,
                    widgets=(same_box, lo_entry, hi_entry))

    def _filter_toggled(self):
        """Sync each row's enabled state, then redraw."""
        self._sync_filter_states()
        self._changed()

    def _sync_filter_states(self):
        for spec in self._filter_vars.values():
            on = spec['on'].get()
            same_box, lo_entry, hi_entry = spec['widgets']
            same_box.configure(state='normal' if on else 'disabled')
            range_state = 'normal' if (on and not spec['same'].get()) else 'disabled'
            lo_entry.configure(state=range_state)
            hi_entry.configure(state=range_state)

    def _build_canvas(self):
        holder = ttk.Frame(self)
        holder.grid(row=0, column=1, sticky='nsew')
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)

        # one Figure for the tab's lifetime — main() clears and redraws it, so
        # repeated previews do not accumulate figures
        self.figure = Figure(figsize=(9, 7), dpi=96)
        self.canvas = FigureCanvasTkAgg(self.figure, master=holder)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew')

        toolbar_holder = ttk.Frame(holder)
        toolbar_holder.grid(row=1, column=0, sticky='ew')
        NavigationToolbar2Tk(self.canvas, toolbar_holder).update()

    # -- data ------------------------------------------------------------

    def _method(self):
        return resolve_estimator(self.method_var.get())['method']

    def _reload_configs(self, event=None):
        """Refill the config list for the current estimator, then redraw."""
        import pandas as pd
        csv = paths.maxr_csv(self._method())
        try:
            names = sorted(set(pd.read_csv(csv)['Config']))
        except Exception:
            names = []

        self._configs = names
        self.config_box.configure(values=names)
        if names and self.config_var.get() not in names:
            self.config_var.set(names[0])
        if not names:
            self.config_var.set('')
            self._show_missing(csv)
            return
        self._changed()

    def _show_missing(self, csv):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.axis('off')
        ax.text(0.5, 0.5,
                f'{Path(csv).name} not found.\n\n'
                'Run the Analysis tab (phase 1) for this estimator first.',
                ha='center', va='center', fontsize=11, color='firebrick')
        self.canvas.draw_idle()
        self.status.configure(text='✗ Missing input table')

    def _filters(self):
        """Current filter selection, or raise ValueError naming the bad field.

        Returns {key: None | (lo, hi)} — the shape config_curve.select_context
        takes, with None meaning "same value as the focus config".
        """
        out = {}
        for key, spec in self._filter_vars.items():
            if not spec['on'].get():
                continue
            if spec['same'].get():
                out[key] = None
                continue

            label = self._filters_spec[key]['label'].replace('same ', '')
            bounds = []
            for var, which in ((spec['lo'], 'from'), (spec['hi'], 'to')):
                raw = var.get().strip()
                if not raw:
                    bounds.append(None)
                    continue
                try:
                    bounds.append(float(raw))
                except ValueError:
                    raise ValueError(f'{label}: {which} value {raw!r} '
                                     'is not a number')

            lo, hi = bounds
            if lo is None and hi is None:
                # range mode with nothing typed yet — treat as no restriction
                # rather than erroring while the user is still filling it in
                continue
            if lo is not None and hi is not None and lo > hi:
                raise ValueError(f'{label}: from {lo:g} is above to {hi:g}')
            out[key] = (lo, hi)
        return out

    # -- drawing ---------------------------------------------------------

    def _first_draw(self):
        self._reload_configs()

    def _changed(self, event=None):
        """Coalesce rapid widget changes into one redraw."""
        if self._dirty:
            return
        self._dirty = True
        self.after(60, self._do_redraw)

    def redraw(self):
        self._dirty = False
        self._do_redraw()

    def _do_redraw(self):
        self._dirty = False
        config = self.config_var.get()
        if not config:
            return

        import config_curve

        # A half-typed range is a normal transient state, not a failure: keep
        # the previous figure on screen and just say what is wrong.
        try:
            filters = self._filters() if self.context_on.get() else None
        except ValueError as exc:
            self.status.configure(text=f'✗ {exc}')
            return

        messages = []
        try:
            result = config_curve.main(
                config,
                target=self.target_var.get(),
                x_axis=self.x_var.get(),
                context=filters,
                radius_method=self._method(),
                save=False,
                fig=self.figure,
                progress=messages.append,
            )
        except Exception as exc:                     # keep the GUI alive
            self._last_error = exc
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.axis('off')
            ax.text(0.5, 0.5, f'Could not draw this figure:\n\n{exc}',
                    ha='center', va='center', fontsize=10, color='firebrick',
                    wrap=True)
            self.canvas.draw_idle()
            self.status.configure(text='✗ Draw failed')
            return

        if result is None:
            # main() reports its own reason through progress
            self.status.configure(text='✗ ' + (messages[-1] if messages
                                               else 'Nothing to draw'))
            self.canvas.draw_idle()
            return

        self.canvas.draw_idle()

        note = next((m for m in messages if 'context:' in m), '')
        self.context_count.configure(text=note.strip())
        self.status.configure(text='Preview — not saved')

    # -- saving ----------------------------------------------------------

    def save(self):
        """Write the figure currently on screen, asking where to put it."""
        config = self.config_var.get()
        if not config:
            return

        import config_curve
        tgt = config_curve.TARGETS[self.target_var.get()]
        method = self._method()
        default_dir = paths.ensure_dir(
            paths.FIGURES_DIR / 'config_curve' / method)
        default_name = paths.suffixed(
            f'{config}_curve_{tgt["token"]}_{self.x_var.get()}.png', method)

        chosen = filedialog.asksaveasfilename(
            title='Save figure', defaultextension='.png',
            initialdir=str(default_dir), initialfile=default_name,
            filetypes=[('PNG image', '*.png'), ('PDF document', '*.pdf'),
                       ('SVG image', '*.svg'), ('All files', '*.*')])
        if not chosen:
            return

        try:
            # bbox_inches keeps the caption below the axes, matching the CLI
            self.figure.savefig(chosen, dpi=150, bbox_inches='tight')
        except Exception as exc:
            messagebox.showerror('Save failed', str(exc))
            self.status.configure(text='✗ Save failed')
            return

        self.status.configure(text=f'✓ Saved {Path(chosen).name}')
