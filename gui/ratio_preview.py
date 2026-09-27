"""Live ratio-map tab: the P/P_ref field for one config, steered not launched.

run_analysis writes one ratio PNG per config as a side effect of phase 1, so
looking at a different colour scale — or at the field without the convergence
circle drawn over it — meant re-running the whole phase for 96 configs and
opening the file again.

This tab draws the same figure (blastlib.plotting.ratio.draw_ratio, shared with
the batch path) into an embedded canvas, and writes a file only when Save is
pressed. Nothing here recomputes the analysis: it reads the same processed NPZ
phase 1 reads and calls the same convergence estimator, so what is on screen is
what phase 1 would have produced for these settings.

One drawing option is deliberately not shared: the preview passes
center_white=True, pinning ratio 1 to white for any manual limits, and rejects
limits that do not straddle 1. The batch keeps the plain linear scale so the
figures it writes stay comparable with the ones already on disk. Auto limits
are symmetric about 1 either way, so the two paths differ only when limits are
typed in here.

Loading is split from drawing on purpose. The NPZ load plus find_convergence_radius
takes long enough to feel (it scans 91 angles), while a redraw is just
pcolormesh over arrays already in memory. So the per-config work is cached and
only the config box and the estimator invalidate it — every other widget
redraws from the cache and is instant.
"""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402
from matplotlib.backends.backend_tkagg import (  # noqa: E402
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure  # noqa: E402

from blastlib import constants, paths  # noqa: E402
from blastlib.config.parser import config_parser  # noqa: E402
from blastlib.geometry import concat3, exclude_radius  # noqa: E402
from blastlib.io.npz_store import load_processed_data  # noqa: E402
from blastlib.plotting.ratio import draw_ratio  # noqa: E402
from blastlib.processing.convergence import find_convergence_radius  # noqa: E402
from blastlib.processing.radius_estimator import (  # noqa: E402
    VALID_METHODS, resolve_estimator)
from blastlib.processing.soft_criterion import (  # noqa: E402
    soft_pressure_fields, soft_pressure_weights)
from gui.specs import available_radius_methods  # noqa: E402

# Panel selections offered, as (label, panel tuple for draw_ratio).
PANEL_CHOICES = [
    ('Pressure + Impulse', ('P', 'I')),
    ('Pressure only', ('P',)),
    ('Impulse only', ('I',)),
]


class RatioPreviewTab(ttk.Frame):
    """Controls on the left, live ratio map on the right."""

    def __init__(self, master, spec):
        super().__init__(master, padding=8)
        self.spec = spec
        self._cache = None       # (config, method) -> loaded arrays
        self._cache_key = None
        self._dirty = False
        self._typing_job = None  # pending after() for a numeric field

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_controls()
        self._build_canvas()
        self._sync_scale_states()

        self.after(50, self._reload_configs)

    # -- construction ----------------------------------------------------

    def _build_controls(self):
        side = ttk.Frame(self)
        side.grid(row=0, column=0, sticky='nsw', padx=(0, 10))
        side.columnconfigure(1, weight=1)

        row = 0
        if self.spec.get('blurb'):
            ttk.Label(side, text=self.spec['blurb'], wraplength=260,
                      foreground='gray25').grid(row=row, column=0, columnspan=2,
                                                sticky='w', pady=(0, 8))
            row += 1

        ttk.Label(side, text='Config:').grid(row=row, column=0, sticky='w')
        self.config_var = tk.StringVar()
        self.config_box = ttk.Combobox(side, textvariable=self.config_var,
                                       width=32, state='readonly')
        self.config_box.grid(row=row, column=1, sticky='ew', pady=2)
        # a different config invalidates the cache, so this reloads rather
        # than just redrawing
        self.config_box.bind('<<ComboboxSelected>>', lambda e: self._reload())
        row += 1

        ttk.Label(side, text='Estimator:').grid(row=row, column=0, sticky='w')
        self.method_var = tk.StringVar(
            value=constants.RADIUS_ESTIMATOR['method'])
        mbox = ttk.Combobox(side, textvariable=self.method_var, width=32,
                            state='readonly',
                            values=available_radius_methods())
        mbox.grid(row=row, column=1, sticky='ew', pady=2)
        # rescan tokens whenever the list drops down, so a soft run finished
        # in the Analysis tab appears here without restarting the launcher
        mbox.configure(postcommand=lambda:
                       mbox.configure(values=available_radius_methods()))
        # the estimator changes the radius itself — recompute, not redraw
        mbox.bind('<<ComboboxSelected>>', lambda e: self._reload())
        row += 1

        ttk.Label(side, text='Panels:').grid(row=row, column=0, sticky='w')
        self.panels_var = tk.StringVar(value=PANEL_CHOICES[0][0])
        pbox = ttk.Combobox(side, textvariable=self.panels_var, width=32,
                            state='readonly',
                            values=[c[0] for c in PANEL_CHOICES])
        pbox.grid(row=row, column=1, sticky='ew', pady=2)
        pbox.bind('<<ComboboxSelected>>', self._changed)
        row += 1

        # -- which field is drawn
        field = ttk.LabelFrame(side, text='Field', padding=6)
        field.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        row += 1

        self.raw_on = tk.BooleanVar(value=False)
        ttk.Checkbutton(field, text='Raw ratio (before the pinning)',
                        variable=self.raw_on,
                        command=self._changed).grid(row=0, column=0, sticky='w')
        ttk.Label(field, text='The stored ratio is forced to exactly 1 wherever '
                              'P < minPressure or |P - P_ref| < minPressure, '
                              'which covers most of the domain. Raw is the '
                              'field before that, so it shows what the '
                              'criterion decided to ignore.',
                  foreground='gray', wraplength=260).grid(
                      row=1, column=0, sticky='w', pady=(4, 0))
        ttk.Label(field, text='The radius and boundary are not recomputed — '
                              'they stay the criterion\'s answer on the pinned '
                              'field. The gap is what you are looking at.',
                  foreground='gray25', wraplength=260).grid(
                      row=2, column=0, sticky='w', pady=(4, 0))

        # -- overlays
        group = ttk.LabelFrame(side, text='Overlays', padding=6)
        group.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        row += 1

        self.radius_on = tk.BooleanVar(value=True)
        ttk.Checkbutton(group, text='Measured convergence radius',
                        variable=self.radius_on,
                        command=self._changed).grid(row=0, column=0, sticky='w')
        self.polyline_on = tk.BooleanVar(value=False)
        ttk.Checkbutton(group, text='Per-θ convergence boundary',
                        variable=self.polyline_on,
                        command=self._changed).grid(row=1, column=0, sticky='w')
        self.buildings_on = tk.BooleanVar(value=True)
        ttk.Checkbutton(group, text='Building footprints',
                        variable=self.buildings_on,
                        command=self._changed).grid(row=2, column=0, sticky='w')
        ttk.Label(group, text='The boundary is the 91 per-angle radii joined '
                              'up; the circle is the single radius they '
                              'collapse to. The gap between them is the shape '
                              'the collapse throws away.',
                  foreground='gray', wraplength=260).grid(
                      row=3, column=0, sticky='w', pady=(4, 0))
        ttk.Label(group, text='Turning both off leaves the bare ratio field, '
                              'with nothing drawn over it.',
                  foreground='gray', wraplength=260).grid(
                      row=4, column=0, sticky='w', pady=(4, 0))

        # -- colour scale
        scale = ttk.LabelFrame(side, text='Colour scale  (ratio = 1 is white)',
                               padding=6)
        scale.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        row += 1

        self.scale_mode = tk.StringVar(value='auto')
        for i, (val, text) in enumerate((
                ('auto', 'Auto (95th pct of |ratio-1|)'),
                ('manual', 'Manual limits'))):
            ttk.Radiobutton(scale, text=text, value=val,
                            variable=self.scale_mode,
                            command=self._scale_toggled).grid(
                                row=i, column=0, columnspan=4, sticky='w')

        ttk.Label(scale, text='min', foreground='gray').grid(row=2, column=1)
        ttk.Label(scale, text='max', foreground='gray').grid(row=2, column=2)

        self.limits = {}
        note_row = 5
        for i, (key, text) in enumerate((('P', 'P / P_ref'),
                                         ('I', 'I / I_ref')), start=3):
            ttk.Label(scale, text=text).grid(row=i, column=0, sticky='w')
            lo, hi = tk.StringVar(value='0.5'), tk.StringVar(value='1.5')
            lo_e = ttk.Entry(scale, textvariable=lo, width=7)
            hi_e = ttk.Entry(scale, textvariable=hi, width=7)
            lo_e.grid(row=i, column=1, padx=2, pady=1)
            hi_e.grid(row=i, column=2, padx=2, pady=1)
            for var in (lo, hi):
                var.trace_add('write', self._typed)
            self.limits[key] = dict(lo=lo, hi=hi, widgets=(lo_e, hi_e))

        ttk.Label(scale, text='Each range must straddle 1. The two sides are '
                              'stretched separately, so 1 stays white even '
                              'when the range is lopsided.',
                  foreground='gray', wraplength=260).grid(
                      row=note_row, column=0, columnspan=4, sticky='w',
                      pady=(4, 0))

        # -- zoom
        zoom = ttk.LabelFrame(side, text='Extent', padding=6)
        zoom.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        row += 1

        ttk.Label(zoom, text='Half-width [m]:').grid(row=0, column=0, sticky='w')
        self.extent_var = tk.StringVar()
        ent = ttk.Entry(zoom, textvariable=self.extent_var, width=8)
        ent.grid(row=0, column=1, sticky='w', padx=(4, 0))
        self.extent_var.trace_add('write', self._typed)
        ttk.Label(zoom, text='Blank = auto (largest radius + 15 m).',
                  foreground='gray', wraplength=260).grid(
                      row=1, column=0, columnspan=2, sticky='w', pady=(4, 0))

        # -- actions
        bar = ttk.Frame(side)
        bar.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(12, 0))
        ttk.Button(bar, text='Save figure', width=14,
                   command=self.save).pack(side='left')
        ttk.Button(bar, text='Redraw', width=10,
                   command=self.redraw).pack(side='left', padx=(6, 0))
        row += 1

        self.radius_note = ttk.Label(side, text='', foreground='gray25',
                                     wraplength=260)
        self.radius_note.grid(row=row, column=0, columnspan=2, sticky='w',
                              pady=(8, 0))
        row += 1

        self.status = ttk.Label(side, text='', wraplength=260)
        self.status.grid(row=row, column=0, columnspan=2, sticky='w', pady=(4, 0))

    def _build_canvas(self):
        holder = ttk.Frame(self)
        holder.grid(row=0, column=1, sticky='nsew')
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)

        # one Figure for the tab's lifetime — draw_ratio clears and redraws it,
        # so repeated previews do not accumulate figures
        self.figure = Figure(figsize=(12, 5), dpi=96)
        self.canvas = FigureCanvasTkAgg(self.figure, master=holder)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew')

        toolbar_holder = ttk.Frame(holder)
        toolbar_holder.grid(row=1, column=0, sticky='ew')
        # the toolbar's pan/zoom is the fine control; the Extent box is the
        # coarse one that also survives a redraw
        NavigationToolbar2Tk(self.canvas, toolbar_holder).update()

    def _scale_toggled(self):
        self._sync_scale_states()
        self._changed()

    def _sync_scale_states(self):
        state = 'normal' if self.scale_mode.get() == 'manual' else 'disabled'
        for spec in self.limits.values():
            for widget in spec['widgets']:
                widget.configure(state=state)

    # -- data ------------------------------------------------------------

    def _method(self):
        return resolve_estimator(self.method_var.get())['method']

    def _reload_configs(self):
        """Fill the config list from the NPZ folder, then load the first."""
        npz_dir = Path(paths.default_npz_dir())
        names = sorted(p.stem for p in npz_dir.glob('config_*.npz'))

        self.config_box.configure(values=names)
        if not names:
            self.config_var.set('')
            self._message(
                f'No config_*.npz found in\n{npz_dir}\n\n'
                'Build them on the Preprocess tab, or copy an existing '
                'processed set into data/processed_npz/ (see README).')
            return
        if self.config_var.get() not in names:
            self.config_var.set(names[0])
        self._reload()

    def _load(self):
        """Arrays + convergence radius for the current config and estimator.

        Cached on (config, estimator): those two are the only inputs that change
        the numbers. Every other widget only affects how they are drawn, so it
        must not pay for find_convergence_radius again.
        """
        config = self.config_var.get()
        est = resolve_estimator(self.method_var.get())
        method = est['method']       # soft tokens carry their beta, so the
        key = (config, method)       # cache key distinguishes betas too
        if self._cache_key == key:
            return self._cache

        cfg = config_parser(config)
        if cfg is None:
            raise ValueError(f'could not parse the config name {config!r}')

        # Soft estimators need the raw band fields the weights come from: the
        # v3 raw store builds them on load, the v2 superset stores them
        # (run_phase1 resolves the folder the same way).
        soft = est.get('soft_beta') is not None
        npz_dir = paths.default_npz_dir(soft=soft)
        data, ok = load_processed_data(npz_dir, config)
        if not ok:
            if soft:
                raise ValueError(
                    f'could not load {config}.npz from {npz_dir} — the soft '
                    'criterion needs the raw band fields; build the raw store '
                    'on the Preprocess tab')
            raise ValueError(f'could not load {config}.npz — re-run '
                             'run_preprocess.py, or check the file is complete')

        soft_w = None
        if soft:
            try:
                fields = soft_pressure_fields(data)
            except KeyError as exc:      # v2 keys absent — explain, not crash
                raise ValueError(str(exc))
            soft_w = soft_pressure_weights(fields, est['soft_beta'])

        # the same call phase 1 makes, so the circle drawn here is the radius
        # that run_analysis would have written to the convergence table
        radius = find_convergence_radius(
            concat3(data, 'ratioP{}'), concat3(data, 'ratioI{}'),
            data['peakP_all'], data['peakI_all'],
            concat3(data, 'X{}'), concat3(data, 'Z{}'),
            exclude_radius(cfg), estimator=est, soft_w_P=soft_w)

        self._cache = (data, cfg, radius, method)
        self._cache_key = key
        return self._cache

    def _scale_limits(self):
        """Manual colour limits, or None for auto. Raises ValueError if bad."""
        if self.scale_mode.get() != 'manual':
            return None

        out = {}
        for key, spec in self.limits.items():
            bounds = []
            for var, which in ((spec['lo'], 'min'), (spec['hi'], 'max')):
                raw = var.get().strip()
                try:
                    bounds.append(float(raw))
                except ValueError:
                    raise ValueError(f'{key} {which} {raw!r} is not a number')
            lo, hi = bounds
            if lo >= hi:
                raise ValueError(f'{key}: min {lo:g} must be below max {hi:g}')
            # The preview pins 1 to white, which needs it inside the range. A
            # one-sided range is nearly always a typo, and on a diverging
            # colormap it would read as a plausible but wrong picture — so it
            # is rejected here rather than quietly drawn without a white point.
            if not lo < 1 < hi:
                raise ValueError(
                    f'{key}: range {lo:g}–{hi:g} must straddle 1, so that '
                    'ratio 1 stays white')
            out[key] = (lo, hi)
        return out

    def _axis_limit(self):
        """Manual half-width, or None for the batch rule. Raises ValueError."""
        raw = self.extent_var.get().strip()
        if not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            raise ValueError(f'extent {raw!r} is not a number')
        if value <= 0:
            raise ValueError('extent must be positive')
        return value

    # -- drawing ---------------------------------------------------------

    def _message(self, text, colour='firebrick'):
        """Replace the figure with a single centred message."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.axis('off')
        ax.text(0.5, 0.5, text, ha='center', va='center', fontsize=11,
                color=colour, wrap=True)
        self.canvas.draw_idle()

    def _reload(self, event=None):
        """Config or estimator changed: drop the cache and redraw."""
        self._cache_key = None
        self._changed()

    def _typed(self, *_):
        """A keystroke in a numeric field.

        Redrawing this figure costs the better part of a second (three
        pcolormesh layers, then rasterising them), so unlike the click
        handlers this waits out the typing instead of queueing one redraw per
        character — each keystroke pushes the deadline back.
        """
        if self._typing_job is not None:
            self.after_cancel(self._typing_job)
        self._typing_job = self.after(450, self._typing_settled)

    def _typing_settled(self):
        self._typing_job = None
        self._changed()

    def _changed(self, event=None):
        """Coalesce rapid widget changes into one redraw."""
        if self._dirty:
            return
        self._dirty = True
        self.after(60, self._do_redraw)

    def redraw(self):
        """Redraw now, cancelling any wait still running on a typed field."""
        if self._typing_job is not None:
            self.after_cancel(self._typing_job)
            self._typing_job = None
        self._dirty = False
        self._do_redraw()

    def _do_redraw(self):
        self._dirty = False
        if not self.config_var.get():
            return

        # A half-typed limit is a normal transient state, not a failure: keep
        # the previous figure on screen and just say what is wrong.
        try:
            scale_limits = self._scale_limits()
            axis_limit = self._axis_limit()
        except ValueError as exc:
            self.status.configure(text=f'✗ {exc}')
            # The figure still shows the last good draw, which may be a
            # different config than the box now names. Say so rather than
            # leaving that config's radii sitting under a stale picture.
            if self._cache_key != (self.config_var.get(), self._method()):
                self.radius_note.configure(
                    text='Showing the previous config — fix the value above.')
            return

        loading = self._cache_key is None
        if loading:
            # the only slow step; say so before blocking the event loop on it
            self.status.configure(text='Loading NPZ…')
            self.update_idletasks()

        try:
            data, cfg, radius, method = self._load()
        except Exception as exc:
            self._message(f'Could not load this config:\n\n{exc}')
            self.status.configure(text='✗ Load failed')
            self.radius_note.configure(text='')
            return

        panels = dict(PANEL_CHOICES)[self.panels_var.get()]

        try:
            used = draw_ratio(
                self.figure, data, cfg, self.config_var.get(), radius,
                scale_limits=scale_limits, method=method, panels=panels,
                show_radius=self.radius_on.get(),
                axis_limit=axis_limit,
                show_buildings=self.buildings_on.get(),
                center_white=True,
                show_polyline=self.polyline_on.get(),
                use_raw=self.raw_on.get())
        except Exception as exc:
            self._message(f'Could not draw this figure:\n\n{exc}')
            self.status.configure(text='✗ Draw failed')
            return

        self.figure.tight_layout()
        self.canvas.draw_idle()

        # state the radii even when the circle is hidden — the toggle is about
        # the overlay, not about withholding the number
        self.radius_note.configure(
            text=f'R_conv({method})   P: {_metres(radius["pressure"])}   '
                 f'I: {_metres(radius["impulse"])}\nExtent: {used:g} m')
        self.status.configure(text='Preview — not saved')

    # -- saving ----------------------------------------------------------

    def save(self):
        """Write the figure currently on screen, asking where to put it."""
        config = self.config_var.get()
        if not config:
            return

        method = self._method()
        default_dir = paths.ensure_dir(paths.FIGURES_DIR / method / 'ratio')

        chosen = filedialog.asksaveasfilename(
            title='Save figure', defaultextension='.png',
            initialdir=str(default_dir),
            # the raw view is a different quantity, so it must not default to
            # a filename that overwrites the normal figure
            initialfile=f'{config}_ratio{"_raw" if self.raw_on.get() else ""}.png',
            filetypes=[('PNG image', '*.png'), ('PDF document', '*.pdf'),
                       ('SVG image', '*.svg'), ('All files', '*.*')])
        if not chosen:
            return

        try:
            self.figure.savefig(chosen, dpi=150, bbox_inches='tight')
        except Exception as exc:
            messagebox.showerror('Save failed', str(exc))
            self.status.configure(text='✗ Save failed')
            return

        self.status.configure(text=f'✓ Saved {Path(chosen).name}')


def _metres(value):
    """Format a radius, tolerating the NaN an unresolved config leaves."""
    return '—' if np.isnan(value) else f'{value:.1f} m'
