"""Reusable presentation pieces for the launcher.

Pure widgets — no threading, no pipeline calls. Restyling should only need
changes in this file and app.py.
"""

import tkinter as tk
from tkinter import ttk, filedialog


class LogPane(ttk.Frame):
    """Read-only scrollable text area for a tool's output."""

    def __init__(self, master, height=18):
        super().__init__(master)
        self.text = tk.Text(self, height=height, wrap='none',
                            state='disabled', font=('Consolas', 9))
        yscroll = ttk.Scrollbar(self, orient='vertical', command=self.text.yview)
        xscroll = ttk.Scrollbar(self, orient='horizontal', command=self.text.xview)
        self.text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.text.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def append(self, lines):
        """Append one string or an iterable of strings, then scroll to the end."""
        if isinstance(lines, str):
            lines = [lines]
        lines = list(lines)
        if not lines:
            return
        at_bottom = self.text.yview()[1] > 0.999
        self.text.configure(state='normal')
        self.text.insert('end', '\n'.join(lines) + '\n')
        self.text.configure(state='disabled')
        if at_bottom:
            self.text.see('end')

    def clear(self):
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.configure(state='disabled')


class Disclosure(ttk.Frame):
    """A collapsible section with a toggle button."""

    def __init__(self, master, title, expanded=False):
        super().__init__(master)
        self._title = title
        self._expanded = tk.BooleanVar(value=expanded)
        self._button = ttk.Button(self, width=24, command=self.toggle)
        self._button.grid(row=0, column=0, sticky='w')
        self.body = ttk.Frame(self)
        self.columnconfigure(0, weight=1)
        self._sync()

    def toggle(self):
        self._expanded.set(not self._expanded.get())
        self._sync()

    def _sync(self):
        if self._expanded.get():
            self._button.configure(text=f'▾  {self._title}')
            self.body.grid(row=1, column=0, sticky='ew', padx=(12, 0), pady=(4, 0))
        else:
            self._button.configure(text=f'▸  {self._title}')
            self.body.grid_forget()


class ParamField:
    """One parameter's widget(s) plus the logic to read its value back.

    ``cast`` converts the raw string; ``empty_is_none`` maps a blank entry to
    None so the underlying function falls back to its own default.
    """

    def __init__(self, master, spec, row):
        self.spec = spec
        self.kind = spec.get('kind', 'text')
        self.key = spec['key']
        self.var = tk.StringVar(value='' if spec.get('default') is None
                                else str(spec['default']))

        label = ttk.Label(master, text=spec['label'] + ':')
        label.grid(row=row, column=0, sticky='w', padx=(0, 8), pady=2)

        self.widget = self._build(master, row)

        help_text = spec.get('help')
        if help_text:
            ttk.Label(master, text=help_text, foreground='gray').grid(
                row=row, column=3, sticky='w', padx=(8, 0))

    def _build(self, master, row):
        if self.kind == 'choice':
            w = ttk.Combobox(master, textvariable=self.var, state='readonly',
                             values=self.spec['options'], width=14)
            w.grid(row=row, column=1, sticky='w', pady=2)
            return w

        if self.kind == 'combo':
            frame = ttk.Frame(master)
            frame.grid(row=row, column=1, columnspan=2, sticky='ew', pady=2)
            box = ttk.Combobox(frame, textvariable=self.var, width=44)
            box.pack(side='left')
            ttk.Button(frame, text='Refresh', width=9,
                       command=self.refresh_options).pack(side='left', padx=(4, 0))
            self._box = box
            self.refresh_options()
            return frame

        if self.kind == 'path':
            frame = ttk.Frame(master)
            frame.grid(row=row, column=1, columnspan=2, sticky='ew', pady=2)
            ttk.Entry(frame, textvariable=self.var, width=46).pack(side='left')
            ttk.Button(frame, text='Browse', width=9,
                       command=self._browse).pack(side='left', padx=(4, 0))
            return frame

        width = 12 if self.kind in ('int', 'float') else 46
        w = ttk.Entry(master, textvariable=self.var, width=width)
        w.grid(row=row, column=1, sticky='w', pady=2)
        return w

    def refresh_options(self):
        """Re-run the spec's options_fn (combo fields only)."""
        fn = self.spec.get('options_fn')
        if fn is None:
            return
        try:
            values = list(fn())
        except Exception:
            values = []
        self._box.configure(values=values)

    def _browse(self):
        if self.spec.get('browse') == 'file':
            chosen = filedialog.askopenfilename(title=self.spec['label'])
        else:
            chosen = filedialog.askdirectory(title=self.spec['label'])
        if chosen:
            self.var.set(chosen)

    def value(self):
        """Return the converted value, or raise ValueError with a clear message."""
        raw = self.var.get().strip()

        if not raw:
            if self.spec.get('required'):
                raise ValueError(f'{self.spec["label"]} is required.')
            return None            # let the callee apply its own default

        cast = self.spec.get('cast')
        if cast is None:
            cast = {'int': int, 'float': float}.get(self.kind)
        if cast is None:
            return raw
        try:
            return cast(raw)
        except ValueError:
            raise ValueError(f'{self.spec["label"]}: {raw!r} is not a valid '
                             f'{"integer" if cast is int else "number"}.')


class RadiusEstimatorField:
    """Radio group choosing how per-angle radii collapse to one radius.

    Produces the {'method', 'percentile'} dict that
    processing.radius_estimator.resolve_estimator consumes — the same shape the
    CLI builds and the same default lives in constants.RADIUS_ESTIMATOR, so
    there is exactly one implementation of the setting.

    The percentile spinbox only applies to the percentile method, so it is
    disabled otherwise (same idiom as ScaleField's manual limits).
    """

    METHODS = [('Req (equivalent area)', 'req'),
               ('Max',                   'max'),
               ('Percentile',            'p95')]

    def __init__(self, master, spec, row):
        self.spec = spec
        self.key = spec['key']

        default = spec.get('default') or {}
        self.method = tk.StringVar(value=default.get('method', 'req'))
        self.percentile = tk.StringVar(value=str(default.get('percentile', 95)))

        ttk.Label(master, text=spec['label'] + ':').grid(
            row=row, column=0, sticky='w', padx=(0, 8), pady=2)

        frame = ttk.Frame(master)
        frame.grid(row=row, column=1, columnspan=3, sticky='w', pady=2)

        for label, value in self.METHODS:
            ttk.Radiobutton(frame, text=label, variable=self.method,
                            value=value, command=self._sync).pack(side='left',
                                                                  padx=(0, 10))

        self._spin = ttk.Spinbox(frame, textvariable=self.percentile,
                                 from_=1, to=100, width=5)
        self._spin.pack(side='left')

        self._sync()

    def _sync(self):
        self._spin.configure(
            state='normal' if self.method.get().startswith('p') else 'disabled')

    def value(self):
        method = self.method.get()
        if not method.startswith('p'):
            return {'method': method}
        try:
            p = float(self.percentile.get().strip())
        except ValueError:
            raise ValueError('Percentile must be a number.')
        if not 0 <= p <= 100:
            raise ValueError('Percentile must be between 0 and 100.')
        return {'method': 'percentile', 'percentile': p}


class ScaleField:
    """The auto/manual colour-scale group used by the Analysis tab.

    Produces either None (auto) or {'P': (lo, hi), 'I': (lo, hi)}.
    """

    def __init__(self, master, spec, row):
        self.spec = spec
        self.key = spec['key']
        self.mode = tk.StringVar(value='auto')
        self.limits = {name: tk.StringVar(value=val)
                       for name, val in (('p_lo', '0.5'), ('p_hi', '1.5'),
                                         ('i_lo', '0.5'), ('i_hi', '1.5'))}

        ttk.Label(master, text=spec['label'] + ':').grid(
            row=row, column=0, sticky='w', padx=(0, 8), pady=2)

        frame = ttk.Frame(master)
        frame.grid(row=row, column=1, columnspan=3, sticky='w', pady=2)

        ttk.Radiobutton(frame, text='Auto', variable=self.mode, value='auto',
                        command=self._sync).pack(side='left')
        ttk.Radiobutton(frame, text='Manual', variable=self.mode, value='manual',
                        command=self._sync).pack(side='left', padx=(8, 12))

        self._entries = []
        for label, keys in (('P', ('p_lo', 'p_hi')), ('I', ('i_lo', 'i_hi'))):
            ttk.Label(frame, text=f'{label}:').pack(side='left')
            for k in keys:
                e = ttk.Entry(frame, textvariable=self.limits[k], width=6)
                e.pack(side='left', padx=2)
                self._entries.append(e)
            ttk.Label(frame, text='  ').pack(side='left')

        self._sync()

    def _sync(self):
        state = 'normal' if self.mode.get() == 'manual' else 'disabled'
        for e in self._entries:
            e.configure(state=state)

    def value(self):
        if self.mode.get() == 'auto':
            return None
        try:
            nums = {k: float(v.get().strip()) for k, v in self.limits.items()}
        except ValueError:
            raise ValueError('Manual scale limits must all be numbers.')
        return {'P': (nums['p_lo'], nums['p_hi']),
                'I': (nums['i_lo'], nums['i_hi'])}
