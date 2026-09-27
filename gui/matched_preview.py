"""Interactive matched-set explorer.

Every other analysis tab is run-and-log: press Run, a worker thread calls a
pipeline function, output scrolls past. That shape does not fit this tool. The
question it answers — "does W push the radius the same way at every street
width?" — is asked by changing a filter and looking, then changing it again.
So this tab embeds a matplotlib canvas and replots on every widget change,
like the Config Curve and Ratio Map tabs.

Redrawing happens on the main thread. The whole computation is a groupby over
96 rows plus a few dozen short lines, which is far below the latency where a
worker thread and its blit-back would earn their complexity.

The data layer is gui/matched_sets.py; this file is only widgets and drawing.
Reads outputs/tables/convergence_table_req.csv exclusively — never a SHIPPED_,
_p95 or unsuffixed table — and nothing here fits a model.
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
from matplotlib.lines import Line2D  # noqa: E402

from blastlib import paths  # noqa: E402
from gui import matched_sets as ms  # noqa: E402

# The one table this tool is allowed to read. Stated here rather than derived
# from the estimator setting: the spec pins the tool to req, so a GUI-wide
# estimator change must not silently repoint it at another file.
TABLE_NAME = 'convergence_table_req.csv'

# Discrete colour cycle for categorical colour-by. Pi2 is continuous and gets
# a colourmap instead.
_PALETTE = ['tab:blue', 'tab:red', 'tab:green', 'tab:orange', 'tab:purple',
            'tab:brown', 'tab:pink', 'tab:olive', 'tab:cyan', 'k']


class MatchedSetsTab(ttk.Frame):
    """Controls on the left, live matched-set plot on the right."""

    def __init__(self, master, spec):
        super().__init__(master, padding=8)
        self.spec = spec
        self.df = None
        self._lines = []          # plotted sets, parallel to self._artists
        self._artists = []
        self._stats = {}
        self._dirty = False
        self._typing_job = None
        self._load_error = None

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_controls()
        self._build_canvas()

        self.after(50, self._first_draw)

    # -- construction ----------------------------------------------------

    def _build_controls(self):
        # The filter stack is taller than most screens, so the controls live in
        # a scrollable canvas rather than being clipped at the bottom.
        outer = ttk.Frame(self)
        outer.grid(row=0, column=0, sticky='nsw', padx=(0, 10))
        outer.rowconfigure(0, weight=1)

        canvas = tk.Canvas(outer, width=290, highlightthickness=0,
                           borderwidth=0)
        scroll = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky='ns')
        scroll.grid(row=0, column=1, sticky='ns')

        side = ttk.Frame(canvas, padding=(0, 0, 8, 0))
        window = canvas.create_window((0, 0), window=side, anchor='nw')
        side.bind('<Configure>',
                  lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',
                    lambda e: canvas.itemconfigure(window, width=e.width))
        self._scroll_canvas = canvas

        row = 0
        if self.spec.get('blurb'):
            ttk.Label(side, text=self.spec['blurb'], wraplength=265,
                      foreground='gray25').grid(row=row, column=0, columnspan=2,
                                                sticky='w', pady=(0, 8))
            row += 1

        # -- what to plot
        ttk.Label(side, text='Vary:').grid(row=row, column=0, sticky='w')
        self.vary_var = tk.StringVar(value='W')
        vbox = ttk.Combobox(side, textvariable=self.vary_var, width=26,
                            state='readonly',
                            values=[f'{k}  —  {v["label"]}'
                                    for k, v in ms.FACTORS.items()])
        vbox.set(f'W  —  {ms.FACTORS["W"]["label"]}')
        vbox.grid(row=row, column=1, sticky='ew', pady=2)
        vbox.bind('<<ComboboxSelected>>', self._vary_changed)
        self._vary_box = vbox
        row += 1

        ttk.Label(side, text='Y axis:').grid(row=row, column=0, sticky='w')
        self.target_var = tk.StringVar(value='R_conv,P')
        tbox = ttk.Combobox(side, textvariable=self.target_var, width=26,
                            state='readonly', values=list(ms.TARGETS))
        tbox.grid(row=row, column=1, sticky='ew', pady=2)
        tbox.bind('<<ComboboxSelected>>', self._changed)
        row += 1

        ttk.Label(side, text='Colour by:').grid(row=row, column=0, sticky='w')
        self.color_var = tk.StringVar(value='s')
        cbox = ttk.Combobox(side, textvariable=self.color_var, width=26,
                            state='readonly', values=['(none)'] + ms.COLOR_BY)
        cbox.grid(row=row, column=1, sticky='ew', pady=2)
        cbox.bind('<<ComboboxSelected>>', self._changed)
        row += 1

        ttk.Label(side, text='Grid block:').grid(row=row, column=0, sticky='w')
        self.block_var = tk.StringVar(value='core')
        bbox = ttk.Combobox(side, textvariable=self.block_var, width=26,
                            state='readonly',
                            values=['core', 'b10', 'both'])
        bbox.grid(row=row, column=1, sticky='ew', pady=2)
        bbox.bind('<<ComboboxSelected>>', self._changed)
        row += 1

        # -- display options
        opts = ttk.LabelFrame(side, text='Display', padding=6)
        opts.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        row += 1

        self.median_on = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text='Overlay median across shown sets',
                        variable=self.median_on,
                        command=self._changed).grid(row=0, column=0, sticky='w')
        self.logy_on = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text='Log y axis', variable=self.logy_on,
                        command=self._changed).grid(row=1, column=0, sticky='w')
        self.scaled_x = tk.BooleanVar(value=False)
        self._scaled_box = ttk.Checkbutton(
            opts, text='Scaled x (H/W^(1/3), s/W^(1/3))',
            variable=self.scaled_x, command=self._changed)
        self._scaled_box.grid(row=2, column=0, sticky='w')

        # -- level filters, one checkbox per level
        self.level_vars = {}
        self._level_frames = {}
        for key in ('det', 'b', 's', 'H', 'W'):
            frame = ttk.LabelFrame(side, text=ms.FACTORS[key]['label'],
                                   padding=6)
            frame.grid(row=row, column=0, columnspan=2, sticky='ew',
                       pady=(8, 0))
            self._level_frames[key] = frame
            row += 1

        # -- derived ranges
        rng = ttk.LabelFrame(side, text='Derived ranges  (blank = no limit)',
                             padding=6)
        rng.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        row += 1
        ttk.Label(rng, text='min', foreground='gray').grid(row=0, column=1)
        ttk.Label(rng, text='max', foreground='gray').grid(row=0, column=2)

        self.range_vars = {}
        for i, (key, spec) in enumerate(ms.DERIVED.items(), start=1):
            ttk.Label(rng, text=spec['label']).grid(row=i, column=0, sticky='w')
            lo, hi = tk.StringVar(), tk.StringVar()
            for col, var in ((1, lo), (2, hi)):
                e = ttk.Entry(rng, textvariable=var, width=7)
                e.grid(row=i, column=col, padx=2, pady=1)
                var.trace_add('write', self._typed)
            self.range_vars[key] = (lo, hi)

        ttk.Label(rng, text='A set is shown only if every member passes.',
                  foreground='gray', wraplength=250).grid(
                      row=99, column=0, columnspan=3, sticky='w', pady=(6, 0))

        # -- actions
        bar = ttk.Frame(side)
        bar.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(12, 0))
        ttk.Button(bar, text='Export PNG + CSV', width=18,
                   command=self.export).pack(side='left')
        ttk.Button(bar, text='Reset', width=8,
                   command=self.reset_filters).pack(side='left', padx=(6, 0))
        row += 1

        self.status = ttk.Label(side, text='', wraplength=265)
        self.status.grid(row=row, column=0, columnspan=2, sticky='w',
                         pady=(8, 0))

        side.columnconfigure(1, weight=1)

    def _build_canvas(self):
        holder = ttk.Frame(self)
        holder.grid(row=0, column=1, sticky='nsew')
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)

        self.figure = Figure(figsize=(9, 6.4), dpi=96)
        self.canvas = FigureCanvasTkAgg(self.figure, master=holder)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew')

        toolbar = ttk.Frame(holder)
        toolbar.grid(row=1, column=0, sticky='ew')
        NavigationToolbar2Tk(self.canvas, toolbar).update()

        # counts panel, and the hover/click readout
        self.counts = ttk.Label(holder, text='', justify='left',
                                font=('Consolas', 9), wraplength=900)
        self.counts.grid(row=2, column=0, sticky='w', pady=(6, 0))
        self.pick = ttk.Label(holder, text='Hover a line to identify its set.',
                              justify='left', foreground='gray25',
                              font=('Consolas', 9), wraplength=900)
        self.pick.grid(row=3, column=0, sticky='w', pady=(2, 0))

        self.canvas.mpl_connect('motion_notify_event', self._on_hover)
        self.canvas.mpl_connect('button_press_event', self._on_click)

    # -- level checkboxes ------------------------------------------------

    def _rebuild_levels(self):
        """Rebuild the level checkboxes from the data.

        Levels depend on the visible block (b = 10 has different s/H/W values),
        so this reruns whenever the block changes. Selections for levels that
        still exist are preserved, so switching block does not silently reset
        an unrelated filter.
        """
        if self.df is None:
            return

        previous = {k: {lvl: v.get() for lvl, v in vars_.items()}
                    for k, vars_ in self.level_vars.items()}

        sub = self.df[self.df['_block'].isin(self._blocks())]
        self.level_vars = {}

        for key, frame in self._level_frames.items():
            for child in frame.winfo_children():
                child.destroy()

            col = ms.FACTORS[key]['col']
            # plain Python scalars, not numpy ones: these become dict keys and
            # are handed to tkinter, which rejects numpy.bool/numpy.int64
            levels = sorted(float(v) for v in sub[col].dropna().unique())
            vars_ = {}
            for i, lvl in enumerate(levels):
                # a level absent before defaults to on, so a newly revealed
                # level does not silently hide data
                on = tk.BooleanVar(value=previous.get(key, {}).get(lvl, True))
                text = (f'det{int(lvl)}' if key == 'det' else ms._fmt(lvl))
                ttk.Checkbutton(frame, text=text, variable=on,
                                command=self._changed).grid(
                                    row=i // 3, column=i % 3, sticky='w',
                                    padx=(0, 8))
                vars_[lvl] = on
            self.level_vars[key] = vars_

            # varying a factor means every level of it is on the x axis, so
            # filtering it would only ever delete whole sets
            state = 'disabled' if key == self._vary() else 'normal'
            for child in frame.winfo_children():
                child.configure(state=state)
            frame.configure(text=ms.FACTORS[key]['label']
                            + ('   (on x axis)' if state == 'disabled' else ''))

    def reset_filters(self):
        """Turn every level back on and clear the ranges."""
        for vars_ in self.level_vars.values():
            for var in vars_.values():
                var.set(True)
        for lo, hi in self.range_vars.values():
            lo.set('')
            hi.set('')
        self.redraw()

    # -- reading the controls --------------------------------------------

    def _vary(self):
        return self.vary_var.get().split(' ')[0].strip()

    def _blocks(self):
        choice = self.block_var.get()
        return ('core', 'b10') if choice == 'both' else (choice,)

    def _filters(self):
        """Current filter selection. Raises ValueError naming a bad field."""
        levels = {}
        for key, vars_ in self.level_vars.items():
            if key == self._vary():
                continue        # on the x axis; see _rebuild_levels
            chosen = [lvl for lvl, var in vars_.items() if var.get()]
            if len(chosen) < len(vars_):
                levels[key] = chosen

        ranges = {}
        for key, (lo_var, hi_var) in self.range_vars.items():
            bounds = []
            for var, which in ((lo_var, 'min'), (hi_var, 'max')):
                raw = var.get().strip()
                if not raw:
                    bounds.append(None)
                    continue
                try:
                    bounds.append(float(raw))
                except ValueError:
                    label = ms.DERIVED[key]['label']
                    raise ValueError(f'{label} {which}: {raw!r} is not a number')
            lo, hi = bounds
            if lo is None and hi is None:
                continue
            if lo is not None and hi is not None and lo > hi:
                raise ValueError(f'{ms.DERIVED[key]["label"]}: '
                                 f'min {lo:g} is above max {hi:g}')
            ranges[key] = (lo, hi)

        return {'levels': levels, 'ranges': ranges}

    # -- events ----------------------------------------------------------

    def _first_draw(self):
        table = Path(paths.TABLES_DIR) / TABLE_NAME
        try:
            self.df = ms.load(table)
            self.df['_block'] = ms.block_of(self.df)
        except Exception as exc:
            self._load_error = exc
            self._message(
                f'Could not read {TABLE_NAME}:\n\n{exc}\n\n'
                'Run the Analysis tab (phase 1) with the req estimator first.')
            self.status.configure(text='✗ Missing input table')
            return

        self._rebuild_levels()
        self.redraw()

    def _vary_changed(self, event=None):
        # normalise 'W  —  Charge weight W' back to the bare key
        self.vary_var.set(self._vary())
        self._rebuild_levels()
        self._changed()

    def _typed(self, *_):
        """Wait out typing in a range box rather than replotting per keystroke."""
        if self._typing_job is not None:
            self.after_cancel(self._typing_job)
        self._typing_job = self.after(400, self._typing_settled)

    def _typing_settled(self):
        self._typing_job = None
        self._changed()

    def _changed(self, event=None):
        """Coalesce rapid widget changes into one replot."""
        if self.df is None:
            return
        # the block controls which levels exist, so rebuild before replotting
        if set(self.level_vars) and self.block_var.get():
            pass
        if self._dirty:
            return
        self._dirty = True
        self.after(50, self._do_redraw)

    def redraw(self):
        if self._typing_job is not None:
            self.after_cancel(self._typing_job)
            self._typing_job = None
        self._dirty = False
        self._do_redraw()

    # -- drawing ---------------------------------------------------------

    def _message(self, text, colour='firebrick'):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.axis('off')
        ax.text(0.5, 0.5, text, ha='center', va='center', fontsize=11,
                color=colour, wrap=True)
        self.canvas.draw_idle()

    def _do_redraw(self):
        self._dirty = False
        if self.df is None:
            return

        vary = self._vary()
        target = self.target_var.get()

        # a half-typed bound is a normal transient state, not a failure
        try:
            filters = self._filters()
        except ValueError as exc:
            self.status.configure(text=f'✗ {exc}')
            return

        # the block filter changes which levels exist; keep the boxes in step
        current = {float(v) for v in
                   self.df[self.df['_block'].isin(self._blocks())]
                   ['ChargeWeight'].unique()}
        if current != set(self.level_vars.get('W', {})):
            self._rebuild_levels()
            try:
                filters = self._filters()
            except ValueError as exc:
                self.status.configure(text=f'✗ {exc}')
                return

        scaled = self.scaled_x.get() and vary in ms.X_SCALED
        self._scaled_box.configure(
            state='normal' if vary in ms.X_SCALED else 'disabled')

        lines, stats = ms.select(self.df, vary, target,
                                 blocks=self._blocks(), filters=filters,
                                 x_scaled=scaled)
        self._lines, self._stats = lines, stats

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if not lines:
            ax.axis('off')
            reason = ('No matched sets exist for this combination.'
                      if stats['total'] == 0 else
                      'Every matched set was excluded by the current filters.')
            extra = ''
            if vary == 'b' and self._blocks() == ('b10',):
                extra = ('\n\nThe b = 10 block has only one building size, '
                         'so varying b needs the core 72.')
            elif filters['ranges'] and stats['dropped_filter']:
                # Pi2 and H/s are not constant within a W- or s-set, so an
                # all-members bound on them can legitimately exclude every set
                # while each set still contains passing members. Say so, since
                # the obvious reading is that the filter is broken.
                varying = [ms.DERIVED[k]['label'] for k in filters['ranges']
                           if not self._constant_within_set(k, vary)]
                if varying:
                    extra = ('\n\n' + ', '.join(varying) + ' changes along a '
                             f'{vary} set, and a set is shown only if every '
                             'member passes. Widen the range.')
            ax.text(0.5, 0.5, reason + extra, ha='center', va='center',
                    fontsize=11, color='firebrick', wrap=True)
            self._artists = []
            self.canvas.draw_idle()
            self._update_counts(vary, target)
            self.status.configure(text='Nothing to plot')
            return

        self._draw_lines(ax, lines, vary)

        if self.median_on.get():
            mx, my = ms.median_line(lines)
            if mx.size:
                ax.plot(mx, my, 'k-', linewidth=2.8, marker='D', markersize=6,
                        zorder=6, label='median of shown sets', alpha=0.85)

        x_label = (ms.X_SCALED[vary]['label'] if scaled else
                   f'{ms.FACTORS[vary]["label"]}'
                   + (f'  [{ms.FACTORS[vary]["unit"]}]'
                      if ms.FACTORS[vary]['unit'] else ''))
        ax.set_xlabel(x_label, fontsize=11)
        ax.set_ylabel(ms.TARGETS[target]['label'], fontsize=11)
        ax.set_yscale('log' if self.logy_on.get() else 'linear')
        ax.grid(True, alpha=0.3, which='both')

        blocks = ' + '.join(ms.BLOCKS[b]['label'] for b in self._blocks())
        ax.set_title(f'{target}  vs  {ms.FACTORS[vary]["label"]}\n'
                     f'{stats["shown"]} of {stats["total"]} matched sets   |   '
                     f'{blocks}',
                     fontsize=12, fontweight='bold')

        if vary == 'det':
            # only two levels, and they are labels not quantities
            ax.set_xticks(sorted({float(v) for ln in lines for v in ln['x']}))
            ax.set_xticklabels([f'det{int(t)}' for t in ax.get_xticks()])

        handles = self._legend_handles(vary)
        if handles:
            ax.legend(handles=handles, fontsize=8, loc='best', framealpha=0.9)

        self.figure.tight_layout()
        self.canvas.draw_idle()

        self._update_counts(vary, target)
        self.status.configure(text='Live view — nothing written until Export')

    def _constant_within_set(self, derived, vary):
        """Whether a derived quantity holds still while *vary* changes.

        Π₂ = s/W^(1/3) depends on s and W, ρ on b and s, H/s on H and s — so
        which of them are constant along a set depends entirely on which factor
        is being varied. Used only to word the empty-state message.
        """
        depends = {'Pi2': {'s', 'W'}, 'rho': {'b', 's'}, 'H/s': {'H', 's'}}
        return vary not in depends.get(derived, set())

    def _draw_lines(self, ax, lines, vary):
        """One line per matched set, coloured by the colour-by control."""
        key = self.color_var.get()
        self._artists = []

        if key in ('(none)', ''):
            for ln in lines:
                self._artists.append(self._plot_one(ax, ln, 'tab:blue'))
            self._color_key, self._color_map = None, {}
            return

        if key == 'Pi2':
            # continuous: colour by the set's mean Pi2 through a colourmap
            import matplotlib.cm as cm
            import matplotlib.colors as mcolors
            values = [float(ln['rows']['Pi2'].mean()) for ln in lines]
            norm = mcolors.Normalize(vmin=min(values), vmax=max(values))
            cmap = cm.get_cmap('viridis')
            for ln, v in zip(lines, values):
                self._artists.append(self._plot_one(ax, ln, cmap(norm(v))))
            sm = cm.ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            self.figure.colorbar(sm, ax=ax, label=ms.DERIVED['Pi2']['label'])
            self._color_key, self._color_map = 'Pi2', {}
            return

        # categorical: one colour per level of the chosen factor. A set is
        # constant in every factor but the varying one, so its colour is
        # well defined unless the colour-by IS the varying factor — in which
        # case the level changes along the line and we fall back to one colour.
        col = ms.FACTORS[key]['col']
        if key == vary:
            for ln in lines:
                self._artists.append(self._plot_one(ax, ln, 'tab:blue'))
            self._color_key, self._color_map = None, {}
            return

        levels = sorted({float(ln['rows'][col].iloc[0]) for ln in lines})
        cmap = {lvl: _PALETTE[i % len(_PALETTE)]
                for i, lvl in enumerate(levels)}
        for ln in lines:
            lvl = float(ln['rows'][col].iloc[0])
            self._artists.append(self._plot_one(ax, ln, cmap[lvl]))
        self._color_key, self._color_map = key, cmap

    def _plot_one(self, ax, line, colour):
        artist, = ax.plot(line['x'], line['y'], '-o', color=colour,
                          linewidth=1.4, markersize=4.5, alpha=0.75,
                          picker=4)
        return artist

    def _legend_handles(self, vary):
        """Legend entries for the current colour-by (plus the median line)."""
        handles = []
        key = getattr(self, '_color_key', None)
        if key and key != 'Pi2':
            label = ms.FACTORS[key]['label']
            for lvl, colour in sorted(self._color_map.items()):
                text = (f'det{int(lvl)}' if key == 'det'
                        else f'{label.split()[-1]} = {ms._fmt(lvl)}')
                handles.append(Line2D([], [], color=colour, marker='o',
                                      linewidth=1.4, markersize=4.5,
                                      label=text))
        if self.median_on.get():
            handles.append(Line2D([], [], color='k', marker='D', linewidth=2.8,
                                  markersize=6, label='median of shown sets'))
        return handles

    def _update_counts(self, vary, target):
        """The text panel: how the shown sets behave."""
        st = self._stats
        if not st:
            self.counts.configure(text='')
            return

        parts = [f'showing {st["shown"]} of {st["total"]} matched sets']
        if st['dropped_filter']:
            parts.append(f'{st["dropped_filter"]} excluded by filters')
        if st['dropped_nan']:
            parts.append(f'{st["dropped_nan"]} dropped for missing/NaN '
                         f'{target}')
        if len(self._blocks()) > 1:
            parts.append('  '.join(f'{ms.BLOCKS[b]["label"]}: {n}'
                                   for b, n in st['by_block'].items() if n))

        step = st['median_pct_step']
        trend = (f'rising {st["rise"]}   falling {st["fall"]}   '
                 f'flat {st["flat"]}   non-monotone {st["mixed"]}')
        median = ('median change per step: '
                  + ('n/a' if np.isnan(step) else f'{step:+.1f}%'))

        self.counts.configure(text='   |   '.join(parts) + '\n'
                              + trend + '   |   ' + median)

    # -- hover / click ---------------------------------------------------

    def _hit(self, event):
        """The set under the cursor, or None."""
        if event.inaxes is None:
            return None
        for artist, line in zip(self._artists, self._lines):
            hit, _ = artist.contains(event)
            if hit:
                return line
        return None

    def _on_hover(self, event):
        line = self._hit(event)
        if line is None:
            self.pick.configure(text='Hover a line to identify its set.',
                                foreground='gray25')
            return
        self.pick.configure(text=ms.describe_line(line, self._vary()),
                            foreground='black')

    def _on_click(self, event):
        line = self._hit(event)
        if line is None:
            return
        # clicking pins the same readout; highlight it so it is findable again
        for artist in self._artists:
            artist.set_linewidth(1.4)
            artist.set_alpha(0.75)
        idx = self._lines.index(line)
        self._artists[idx].set_linewidth(3.2)
        self._artists[idx].set_alpha(1.0)
        self.canvas.draw_idle()
        self.pick.configure(text=ms.describe_line(line, self._vary()),
                            foreground='black')

    # -- export ----------------------------------------------------------

    def _slug(self):
        """Filename encoding the current selection."""
        vary = self._vary()
        target = self.target_var.get().replace(',', '').replace('/', '-')
        bits = [f'vary{vary}', target, '+'.join(self._blocks())]

        for key, vars_ in sorted(self.level_vars.items()):
            if key == vary:
                continue
            chosen = [lvl for lvl, var in vars_.items() if var.get()]
            if len(chosen) < len(vars_):
                bits.append(f'{key}' + '-'.join(ms._fmt(c) for c in chosen))

        for key, (lo, hi) in sorted(self.range_vars.items()):
            lo_s, hi_s = lo.get().strip(), hi.get().strip()
            if lo_s or hi_s:
                safe = key.replace('/', '')
                bits.append(f'{safe}{lo_s or "min"}-{hi_s or "max"}')

        if self.scaled_x.get() and vary in ms.X_SCALED:
            bits.append('scaledx')
        if self.logy_on.get():
            bits.append('logy')

        return 'matched_' + '_'.join(bits)

    def export(self):
        """Write the current view as PNG plus the CSV of the plotted data."""
        if not self._lines:
            messagebox.showinfo('Nothing to export',
                                'No matched sets are currently shown.')
            return

        default_dir = paths.ensure_dir(Path(paths.FIGURES_DIR) / 'matched_sets')
        chosen = filedialog.asksaveasfilename(
            title='Export view (PNG + CSV)', defaultextension='.png',
            initialdir=str(default_dir), initialfile=self._slug() + '.png',
            filetypes=[('PNG image', '*.png'), ('All files', '*.*')])
        if not chosen:
            return

        png = Path(chosen)
        csv = png.with_suffix('.csv')
        try:
            self.figure.savefig(png, dpi=150, bbox_inches='tight')
            frame = ms.table(self._lines, self._vary(), self.target_var.get(),
                             x_scaled=self.scaled_x.get())
            frame.to_csv(csv, index=False)
        except Exception as exc:
            messagebox.showerror('Export failed', str(exc))
            self.status.configure(text='✗ Export failed')
            return

        self.status.configure(text=f'✓ Wrote {png.name} and {csv.name}')
