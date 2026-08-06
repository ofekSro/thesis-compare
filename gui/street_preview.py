"""Live street-model tab: E(r) predicted vs measured, redrawn as you steer.

Same shape as the other preview tabs (see gui/preview.py for the why):
controls on the left, one embedded matplotlib Figure on the right, redraw
on every widget change, nothing written until Save figure. The drawing
itself is blastlib.street.figures.draw_profile — the SAME function the
batch PNG writer uses, so what this tab shows can never drift from the
published figure.

Two steering modes:
  * a stored config — its strip measurement is loaded (once, then cached)
    and overlaid on the prediction;
  * free geometry (b, s, H, W, det) — prediction only, unless the geometry
    happens to match a stored config, whose measurement is then overlaid.

Loading a config's NPZ takes under a second (raw-store expansion); it
happens on the main thread like every other preview tab, and the cache
makes repeat visits instant.
"""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from matplotlib.backends.backend_tkagg import (  # noqa: E402
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure  # noqa: E402

from blastlib import paths  # noqa: E402
from blastlib.config.parser import config_parser  # noqa: E402
from blastlib.street.figures import (  # noqa: E402
    draw_profile, find_matching_config)
from blastlib.street.validation import measured_profile  # noqa: E402


class StreetPreviewTab(ttk.Frame):
    """Controls on the left, live E(r) figure on the right."""

    def __init__(self, master, spec):
        super().__init__(master, padding=8)
        self.spec = spec
        self._meas_cache = {}
        self._configs = []

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_controls()
        self._build_canvas()
        self.after(50, self._first_draw)

    # -- construction ----------------------------------------------------

    def _build_controls(self):
        side = ttk.Frame(self)
        side.grid(row=0, column=0, sticky='nsw', padx=(0, 10))
        row = 0
        if self.spec.get('blurb'):
            ttk.Label(side, text=self.spec['blurb'], wraplength=250,
                      foreground='gray25').grid(row=row, column=0,
                                                columnspan=2, sticky='w',
                                                pady=(0, 8))
            row += 1

        self.mode_var = tk.StringVar(value='config')
        bar = ttk.Frame(side)
        bar.grid(row=row, column=0, columnspan=2, sticky='w', pady=(0, 4))
        for val, text in (('config', 'Stored config'),
                          ('free', 'Free geometry')):
            ttk.Radiobutton(bar, text=text, value=val,
                            variable=self.mode_var,
                            command=self._mode_changed).pack(side='left',
                                                             padx=(0, 8))
        row += 1

        ttk.Label(side, text='Config:').grid(row=row, column=0, sticky='w')
        self.config_var = tk.StringVar()
        self.config_box = ttk.Combobox(side, textvariable=self.config_var,
                                       width=32, state='readonly')
        self.config_box.grid(row=row, column=1, sticky='ew', pady=2)
        self.config_box.bind('<<ComboboxSelected>>', self._changed)
        # rescan on dropdown, so a store built after launch appears here
        self.config_box.configure(postcommand=self._reload_configs)
        row += 1

        self.geo_vars = {}
        for key, label, default in (('b', 'b — building [m]', '15'),
                                    ('s', 's — street [m]', '5'),
                                    ('H', 'H — height [m]', '12'),
                                    ('W', 'W — charge [kg]', '500')):
            ttk.Label(side, text=label).grid(row=row, column=0, sticky='w')
            var = tk.StringVar(value=default)
            entry = ttk.Entry(side, textvariable=var, width=10)
            entry.grid(row=row, column=1, sticky='w', pady=1)
            entry.bind('<Return>', self._changed)
            entry.bind('<FocusOut>', self._changed)
            self.geo_vars[key] = var
            row += 1
        ttk.Label(side, text='det:').grid(row=row, column=0, sticky='w')
        self.det_var = tk.IntVar(value=1)
        dbar = ttk.Frame(side)
        dbar.grid(row=row, column=1, sticky='w', pady=1)
        for val, text in ((1, '1 mid-street'), (2, '2 intersection')):
            ttk.Radiobutton(dbar, text=text, value=val, variable=self.det_var,
                            command=self._changed).pack(side='left',
                                                        padx=(0, 6))
        row += 1

        self.status = ttk.Label(side, text='', wraplength=250,
                                foreground='gray25', justify='left')
        self.status.grid(row=row, column=0, columnspan=2, sticky='w',
                         pady=(8, 0))
        row += 1

        ttk.Button(side, text='Save figure',
                   command=self._save).grid(row=row, column=0, columnspan=2,
                                            sticky='ew', pady=(10, 0))
        self._mode_widgets_state()

    def _build_canvas(self):
        holder = ttk.Frame(self)
        holder.grid(row=0, column=1, sticky='nsew')
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1)
        self.fig = Figure(figsize=(9, 5.5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=holder)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew')
        toolbar = NavigationToolbar2Tk(self.canvas, holder,
                                       pack_toolbar=False)
        toolbar.grid(row=1, column=0, sticky='ew')
        toolbar.update()

    # -- data ------------------------------------------------------------

    def _npz_dir(self):
        return paths.default_npz_dir(soft=True)

    def _reload_configs(self):
        self._configs = sorted(
            p.stem for p in Path(self._npz_dir()).glob('config_*.npz'))
        self.config_box.configure(values=self._configs)

    def _measured(self, name):
        if name not in self._meas_cache:
            self._meas_cache[name] = measured_profile(name, self._npz_dir())
        return self._meas_cache[name]

    # -- events ----------------------------------------------------------

    def _mode_widgets_state(self):
        free = self.mode_var.get() == 'free'
        self.config_box.configure(state='disabled' if free else 'readonly')

    def _mode_changed(self):
        self._mode_widgets_state()
        self._redraw()

    def _changed(self, _event=None):
        self._redraw()

    def _first_draw(self):
        self._reload_configs()
        if self._configs:
            self.config_var.set(self._configs[0])
        self._redraw()

    # -- drawing ---------------------------------------------------------

    def _redraw(self):
        try:
            if self.mode_var.get() == 'config':
                name = self.config_var.get()
                if not name:
                    return
                cfg = config_parser(name)
                b, s, H, W, det = (cfg['bsize'], cfg['swidth'],
                                   cfg['height'], cfg['weight'], cfg['det'])
                meas, title = self._measured(name), name
            else:
                b = float(self.geo_vars['b'].get())
                s = float(self.geo_vars['s'].get())
                H = float(self.geo_vars['H'].get())
                W = float(self.geo_vars['W'].get())
                det = int(self.det_var.get())
                match = find_matching_config(b, s, H, W, det,
                                             self._npz_dir())
                meas = self._measured(match) if match else None
                title = match or f'b{b:g}_s{s:g}_h{H:g}_w{W:g}_det{det}'
            info = draw_profile(self.fig, b, s, H, W, det, meas=meas,
                                title=title)
        except Exception as exc:               # a bad entry must not kill the tab
            self.status.configure(text=f'Error: {exc}', foreground='firebrick')
            return
        self._title = title
        verdict = ('STRONG local zone' if info['strong']
                   else 'no strong local zone')
        text = (f"E_peak = {info['E_peak']:.2f} ({verdict})\n"
                f"R_half = {info['R_half']:.1f} m")
        if info['mape'] is not None:
            text += f"\nchannelling-zone MAPE {info['mape']:.1f}%"
        self.status.configure(text=text, foreground='gray25')
        self.canvas.draw_idle()

    def _save(self):
        initial = f'{getattr(self, "_title", "street_profile")}_E.png'
        path = filedialog.asksaveasfilename(
            defaultextension='.png', initialfile=initial,
            initialdir=paths.fig_dir('e_profile'),
            filetypes=[('PNG image', '*.png')])
        if not path:
            return
        try:
            self.fig.savefig(path, dpi=150, bbox_inches='tight')
        except OSError as exc:
            messagebox.showerror('Save figure', str(exc))
            return
        self.status.configure(text=f'Saved {path}', foreground='gray25')
