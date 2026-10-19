"""Z Bands tab: one config, each cell coloured by the smallest listed Z_free
whose free-field level it reaches (blastlib.processing.z_bands).

Same pattern as the Ratio Map tab: controls on the left, a live figure on the
right, nothing written until Save figure. All numbers come from blastlib:
the per-direction level is the one the phase-1 MaxR loop uses, the cut and the
MaxR / R_conv circles come from the phase-1 tables of the chosen estimator.

Loading is split from drawing: the NPZ is loaded once per (config, estimator)
and the per-direction levels are cached per Z, so editing the Z list computes
only the Z values not seen yet, and colour changes redraw from memory.
"""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, colorchooser

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from matplotlib.backends.backend_tkagg import (  # noqa: E402
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.colors import to_hex  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from blastlib import constants, paths  # noqa: E402
from blastlib.config.parser import config_parser  # noqa: E402
from blastlib.io.npz_store import load_processed_data  # noqa: E402
from blastlib.plotting.z_bands import draw_z_bands, default_band_colors  # noqa: E402
from blastlib.processing import z_bands as zb  # noqa: E402
from blastlib.processing.free_field import load_ff_lookup  # noqa: E402
from blastlib.processing.radius_estimator import resolve_estimator  # noqa: E402
from gui.specs import available_radius_methods  # noqa: E402

PANEL_CHOICES = [
    ('Pressure + Impulse', ('P', 'I')),
    ('Pressure only', ('P',)),
    ('Impulse only', ('I',)),
]
DEFAULT_Z = '2, 4, 6, 8, 12'


class ZBandsTab(ttk.Frame):
    """Controls on the left, live Z-band map on the right."""

    def __init__(self, master, spec):
        super().__init__(master, padding=8)
        self.spec = spec
        self._data_key = None        # (config, method) of the loaded NPZ
        self._data = None            # (processed, cfg)
        self._levels = {'P': {}, 'I': {}}
        self._tables = {}            # method -> (conv, maxr)
        self._ff = None
        self._band_colors = {}       # Z -> colour chosen by the user
        self._below_color = '#f4b183'
        self._building_color = '#8f8e89'
        self._dirty = False
        self._typing_job = None

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_controls()
        self._build_canvas()
        self.after(50, self._reload_configs)

    # -- construction ----------------------------------------------------

    def _build_controls(self):
        side = ttk.Frame(self)
        side.grid(row=0, column=0, sticky='nsw', padx=(0, 10))
        side.columnconfigure(1, weight=1)
        row = 0
        if self.spec.get('blurb'):
            ttk.Label(side, text=self.spec['blurb'], wraplength=260,
                      foreground='gray25').grid(row=row, column=0, columnspan=2, sticky='w', pady=(0, 8))
            row += 1

        ttk.Label(side, text='Config:').grid(row=row, column=0, sticky='w')
        self.config_var = tk.StringVar()
        self.config_box = ttk.Combobox(side, textvariable=self.config_var, width=32, state='readonly')
        self.config_box.grid(row=row, column=1, sticky='ew', pady=2)
        self.config_box.bind('<<ComboboxSelected>>', lambda e: self._reload())
        row += 1

        ttk.Label(side, text='Estimator:').grid(row=row, column=0, sticky='w')
        self.method_var = tk.StringVar(value=constants.RADIUS_ESTIMATOR['method'])
        mbox = ttk.Combobox(side, textvariable=self.method_var, width=32, state='readonly',
                            values=available_radius_methods())
        mbox.grid(row=row, column=1, sticky='ew', pady=2)
        mbox.configure(postcommand=lambda: mbox.configure(values=available_radius_methods()))
        mbox.bind('<<ComboboxSelected>>', lambda e: self._reload())
        row += 1

        ttk.Label(side, text='Panels:').grid(row=row, column=0, sticky='w')
        self.panels_var = tk.StringVar(value=PANEL_CHOICES[0][0])
        pbox = ttk.Combobox(side, textvariable=self.panels_var, width=32, state='readonly',
                            values=[c[0] for c in PANEL_CHOICES])
        pbox.grid(row=row, column=1, sticky='ew', pady=2)
        pbox.bind('<<ComboboxSelected>>', self._changed)
        row += 1

        bar = ttk.Frame(side)
        bar.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        ttk.Button(bar, text='Save figure', width=14, command=self.save).pack(side='left')
        ttk.Button(bar, text='Redraw', width=10, command=self.redraw).pack(side='left', padx=(6, 0))
        row += 1

        # status and note near the top, so errors stay visible in a short window (QA F3)
        self.status = ttk.Label(side, text='', wraplength=260)
        self.status.grid(row=row, column=0, columnspan=2, sticky='w', pady=(4, 0))
        row += 1
        self.note = ttk.Label(side, text='', foreground='gray25', wraplength=260)
        self.note.grid(row=row, column=0, columnspan=2, sticky='w', pady=(2, 0))
        row += 1

        zbox = ttk.LabelFrame(side, text='Bands', padding=6)
        zbox.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        row += 1
        ttk.Label(zbox, text='Z_free list (integers 1–20):').grid(row=0, column=0, columnspan=3, sticky='w')
        self.z_var = tk.StringVar(value=DEFAULT_Z)
        ttk.Entry(zbox, textvariable=self.z_var, width=30).grid(row=1, column=0, columnspan=3, sticky='w', pady=2)
        self.z_var.trace_add('write', self._typed)
        ttk.Label(zbox, text='A cell takes the smallest listed Z whose free-field '
                             'level it reaches (per direction, as the MaxR loop). '
                             'Bands stop at the last Z whose MaxR is inside R_conv.',
                  foreground='gray', wraplength=260).grid(row=2, column=0, columnspan=3, sticky='w', pady=(2, 4))
        self.swatches = ttk.Frame(zbox)
        self.swatches.grid(row=3, column=0, columnspan=3, sticky='w')

        other = ttk.LabelFrame(side, text='Other colours', padding=6)
        other.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        row += 1
        self._below_btn = self._swatch(other, 0, 'weaker than the last band, inside R_conv',
                                       lambda: self._below_color, self._pick_below)
        self._bld_btn = self._swatch(other, 1, 'building', lambda: self._building_color,
                                     self._pick_building)

        zoom = ttk.LabelFrame(side, text='Extent', padding=6)
        zoom.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        row += 1
        ttk.Label(zoom, text='Half-width [m]:').grid(row=0, column=0, sticky='w')
        self.extent_var = tk.StringVar()
        ttk.Entry(zoom, textvariable=self.extent_var, width=8).grid(row=0, column=1, sticky='w', padx=(4, 0))
        self.extent_var.trace_add('write', self._typed)
        ttk.Label(zoom, text='Blank = auto (largest radius + 15 m).', foreground='gray',
                  wraplength=260).grid(row=1, column=0, columnspan=2, sticky='w', pady=(4, 0))

    def _set_status(self, text, error=False):
        """Status line; errors in red (QA F1)."""
        self.status.configure(text=text, foreground='firebrick' if error else '')

    def _swatch(self, parent, r, text, get, cmd):
        """A colour button (tk.Button, so its background shows the colour) + label."""
        btn = tk.Button(parent, width=3, bg=get(), activebackground=get(), relief='solid', bd=1, command=cmd)
        btn.grid(row=r, column=0, sticky='w', pady=1)
        ttk.Label(parent, text=text).grid(row=r, column=1, sticky='w', padx=(6, 0))
        return btn

    def _build_canvas(self):
        holder = ttk.Frame(self)
        holder.grid(row=0, column=1, sticky='nsew')
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        # constrained layout re-lays out on every resize, so the first draw at
        # the initial canvas size cannot leave a stale layout (QA F2)
        self.figure = Figure(figsize=(13, 7), dpi=96, layout='constrained')
        self.canvas = FigureCanvasTkAgg(self.figure, master=holder)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew')
        tb = ttk.Frame(holder)
        tb.grid(row=1, column=0, sticky='ew')
        NavigationToolbar2Tk(self.canvas, tb).update()

    # -- colours ---------------------------------------------------------

    def _colors_for(self, z_list):
        defaults = default_band_colors(len(z_list))
        return {z: self._band_colors.get(z, to_hex(defaults[i])) for i, z in enumerate(z_list)}

    def _rebuild_swatches(self, z_list):
        for w in self.swatches.winfo_children():
            w.destroy()
        cols = self._colors_for(z_list)
        for i, z in enumerate(z_list):
            self._swatch(self.swatches, i, f'Z = {z}', lambda z=z: cols[z],
                         lambda z=z: self._pick_band(z))

    def _pick(self, current, title):
        res = colorchooser.askcolor(color=current, title=title, parent=self)
        return res[1] if res and res[1] else None

    def _pick_band(self, z):
        z_list = self._z_list_or_none() or (z,)
        c = self._pick(self._colors_for(z_list).get(z), f'Colour of band Z = {z}')
        if c:
            self._band_colors[z] = c
            self._rebuild_swatches(z_list)
            self._changed()

    def _pick_below(self):
        c = self._pick(self._below_color, 'Colour: weaker than the last band, inside R_conv')
        if c:
            self._below_color = c
            self._below_btn.configure(bg=c, activebackground=c)
            self._changed()

    def _pick_building(self):
        c = self._pick(self._building_color, 'Colour: buildings')
        if c:
            self._building_color = c
            self._bld_btn.configure(bg=c, activebackground=c)
            self._changed()

    # -- data ------------------------------------------------------------

    def _method(self):
        return resolve_estimator(self.method_var.get())['method']

    def _z_list_or_none(self):
        try:
            return zb.parse_z_list(self.z_var.get())
        except ValueError:
            return None

    def _reload_configs(self):
        npz_dir = Path(paths.default_npz_dir(soft=True))
        names = sorted(p.stem for p in npz_dir.glob('config_*.npz'))
        self.config_box.configure(values=names)
        if not names:
            self.config_var.set('')
            self._message(f'No config_*.npz found in\n{npz_dir}')
            return
        if self.config_var.get() not in names:
            self.config_var.set(names[0])
        self._reload()

    def _load(self, z_list):
        """Processed arrays, cfg, levels for z_list and the phase-1 tables."""
        config, method = self.config_var.get(), self._method()
        if (config, method) != self._data_key:
            cfg = config_parser(config)
            if cfg is None:
                raise ValueError(f'could not parse the config name {config!r}')
            data, ok = load_processed_data(paths.default_npz_dir(soft=True), config)
            if not ok:
                raise ValueError(f'could not load {config}.npz')
            self._data, self._data_key = (data, cfg), (config, method)
            self._levels = {'P': {}, 'I': {}}
        if method not in self._tables:
            self._tables[method] = zb.load_tables(method)
        if self._ff is None:
            self._ff = load_ff_lookup(paths.FF_CSV)
        data, cfg = self._data
        missing = [z for z in z_list if z not in self._levels['P']]
        if missing:
            new = zb.band_levels(data, cfg, method, self._ff, z_values=missing)
            for t in ('P', 'I'):
                self._levels[t].update(new[t])
        return data, cfg, self._tables[method]

    def _axis_limit(self):
        raw = self.extent_var.get().strip()
        if not raw:
            return None
        value = float(raw)
        if value <= 0:
            raise ValueError('extent must be positive')
        return value

    # -- drawing ---------------------------------------------------------

    def _message(self, text, colour='firebrick'):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.axis('off')
        ax.text(0.5, 0.5, text, ha='center', va='center', fontsize=11, color=colour, wrap=True)
        self.canvas.draw_idle()

    def _reload(self, event=None):
        self._data_key = None
        self._changed()

    def _typed(self, *_):
        if self._typing_job is not None:
            self.after_cancel(self._typing_job)
        self._typing_job = self.after(500, self._typing_settled)

    def _typing_settled(self):
        self._typing_job = None
        self._changed()

    def _changed(self, event=None):
        if self._dirty:
            return
        self._dirty = True
        self.after(60, self._do_redraw)

    def redraw(self):
        if self._typing_job is not None:
            self.after_cancel(self._typing_job)
            self._typing_job = None
        self._dirty = False
        self._do_redraw()

    def _do_redraw(self):
        self._dirty = False
        if not self.config_var.get():
            return
        try:
            z_list = zb.parse_z_list(self.z_var.get())
            axis_limit = self._axis_limit()
        except ValueError as exc:
            self._set_status(f'✗ {exc}', error=True)
            return
        self._rebuild_swatches(z_list)
        self._set_status('Loading / computing levels…')
        self.update_idletasks()
        try:
            data, cfg, (conv, maxr) = self._load(z_list)
            result = zb.compute(data, cfg, self.config_var.get(), z_list, self._method(),
                                self._levels, conv, maxr)
        except Exception as exc:
            self._message(f'Could not compute the bands:\n\n{exc}')
            self._set_status('✗ Failed', error=True)
            return
        panels = dict(PANEL_CHOICES)[self.panels_var.get()]
        try:
            draw_z_bands(self.figure, result, self.config_var.get(), panels=panels,
                         band_colors=self._colors_for(z_list), below_color=self._below_color,
                         building_color=self._building_color, axis_limit=axis_limit,
                         method=self._method(),
                         # two side-by-side legends need ~700 px per panel (QA F4)
                         compact=self.canvas.get_tk_widget().winfo_width() / len(panels) < 700)
        except Exception as exc:
            self._message(f'Could not draw this figure:\n\n{exc}')
            self._set_status('✗ Draw failed', error=True)
            return
        self.canvas.draw_idle()
        self.note.configure(text='   '.join(
            f"{t}: cut Z = {result[t]['z_cut']}, R_conv = {result[t]['r_conv']:.1f} m"
            for t in panels))
        self._set_status('Preview — not saved')

    # -- saving ----------------------------------------------------------

    def save(self):
        config = self.config_var.get()
        if not config:
            return
        figs = paths.FIGURES_DIR
        chosen = filedialog.asksaveasfilename(
            title='Save figure', defaultextension='.png',
            initialdir=str(figs if figs.exists() else PROJECT_ROOT),
            initialfile=f'{config}_zbands_{self._method()}.png',
            filetypes=[('PNG image', '*.png'), ('PDF document', '*.pdf'),
                       ('SVG image', '*.svg'), ('All files', '*.*')])
        if not chosen:
            return
        try:
            self.figure.savefig(chosen, dpi=150, bbox_inches='tight')
        except Exception as exc:
            messagebox.showerror('Save failed', str(exc))
            self._set_status('✗ Save failed', error=True)
            return
        self._set_status(f'✓ Saved {Path(chosen).name}')
