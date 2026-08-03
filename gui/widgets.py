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

        if self.kind == 'checks':
            # One checkbutton per option; value() returns the ticked subset.
            # default: True/None = all ticked, else the iterable of names.
            default = self.spec.get('default')
            ticked = set(self.spec['options'] if default in (None, True)
                         else default or ())
            frame = ttk.Frame(master)
            frame.grid(row=row, column=1, columnspan=2, sticky='w', pady=2)
            self._check_vars = {}
            for name in self.spec['options']:
                var = tk.BooleanVar(value=name in ticked)
                ttk.Checkbutton(frame, text=name, variable=var).pack(
                    side='left', padx=(0, 8))
                self._check_vars[name] = var
            return frame

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
        if self.kind == 'checks':
            return tuple(name for name, var in self._check_vars.items()
                         if var.get())

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


class Tooltip:
    """Hover text for a widget — used where a control is disabled and the
    user needs to know why (plain help labels describe enabled controls)."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self._tip = None
        widget.bind('<Enter>', self._show, add='+')
        widget.bind('<Leave>', self._hide, add='+')

    def _show(self, _event=None):
        if self._tip is not None or not self.text:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f'+{x}+{y}')
        tk.Label(self._tip, text=self.text, justify='left', wraplength=360,
                 background='#ffffe0', relief='solid', borderwidth=1,
                 padx=6, pady=4).pack()

    def _hide(self, _event=None):
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


def estimator_value(method, percentile_raw, criterion, beta_raw):
    """Compose the estimator dict from the widget state (pure, testable).

    Hard returns exactly the dicts the field always produced, so a Hard
    selection is bit-identical to the pre-criterion GUI. Soft appends the
    '_soft' token suffix and the beta — the same {'method', 'soft_beta'}
    shape resolve_estimator takes from the CLI's --soft-beta path.
    """
    if not method.startswith('p'):
        base = {'method': method}
    else:
        try:
            p = float(percentile_raw.strip())
        except ValueError:
            raise ValueError('Percentile must be a number.')
        if not 0 <= p <= 100:
            raise ValueError('Percentile must be between 0 and 100.')
        base = {'method': 'percentile', 'percentile': p}

    if criterion != 'soft':
        return base

    try:
        beta = float(beta_raw.strip())
    except ValueError:
        raise ValueError('Soft-criterion beta must be a number.')
    if not 1 <= beta <= 20:
        raise ValueError('Soft-criterion beta must be between 1 and 20.')
    return {**base, 'method': base['method'] + '_soft', 'soft_beta': beta}


class RadiusEstimatorField:
    """Radio group choosing how per-angle radii collapse to one radius,
    plus the convergence-criterion row (hard 10 kPa band vs soft tanh).

    Produces the {'method', 'percentile', 'soft_beta'} dict that
    processing.radius_estimator.resolve_estimator consumes — the same shape the
    CLI builds and the same default lives in constants.RADIUS_ESTIMATOR, so
    there is exactly one implementation of the setting. A Hard selection
    produces exactly the pre-criterion dicts (bit-identical runs).

    The percentile spinbox only applies to the percentile method and the beta
    spinbox only to the soft criterion, so each is disabled otherwise (same
    idiom as ScaleField's manual limits). The Soft option itself is disabled —
    with a tooltip saying why — when spec['soft_status_fn'] reports that the
    v2 raw-field NPZs are unavailable, so a soft run can never start and then
    die on the missing keys mid-pipeline.
    """

    METHODS = [('Req (equivalent area)', 'req'),
               ('Max',                   'max'),
               ('Percentile',            'p95')]

    SOFT_BETA_DEFAULT = 4.0

    @staticmethod
    def _split_default(method, soft_beta=None):
        """('req_soft3', None) -> ('req', 3.0);  ('req', None) -> ('req', None).

        Delegates to the shared token grammar rather than parsing here, so
        the widget and the pipeline can never disagree about a token.
        """
        from blastlib.processing.radius_estimator import _split_soft
        base, beta = _split_soft(method)
        return base, (float(soft_beta) if soft_beta is not None else beta)

    def __init__(self, master, spec, row):
        self.spec = spec
        self.key = spec['key']

        default = spec.get('default') or {}
        # The default token may already carry the soft suffix (production
        # default), so split it: the method radios show the base collapse and
        # the criterion row shows soft + its beta. Without this the widget
        # would read "Hard" while handing back a soft token.
        base, beta = self._split_default(default.get('method', 'req'),
                                         default.get('soft_beta'))
        self.method = tk.StringVar(value=base)
        self.percentile = tk.StringVar(value=str(default.get('percentile', 95)))
        self.criterion = tk.StringVar(value='soft' if beta else 'hard')
        self.beta = tk.StringVar(value=str(beta if beta
                                           else self.SOFT_BETA_DEFAULT))

        ttk.Label(master, text=spec['label'] + ':').grid(
            row=row, column=0, sticky='w', padx=(0, 8), pady=2)

        frame = ttk.Frame(master)
        frame.grid(row=row, column=1, columnspan=3, sticky='w', pady=2)

        method_line = ttk.Frame(frame)
        method_line.grid(row=0, column=0, sticky='w')
        for label, value in self.METHODS:
            ttk.Radiobutton(method_line, text=label, variable=self.method,
                            value=value, command=self._sync).pack(side='left',
                                                                  padx=(0, 10))

        self._spin = ttk.Spinbox(method_line, textvariable=self.percentile,
                                 from_=1, to=100, width=5)
        self._spin.pack(side='left')

        # -- criterion line: hard band vs soft tanh projection
        # The spec may inject its own availability probe; without one, fall
        # back to probing the default v2 folder directly (lazy import — the
        # only pipeline knowledge in this module, and only because a Soft
        # option that cannot actually run must never be offered).
        status_fn = spec.get('soft_status_fn')
        if status_fn is None:
            def status_fn():
                from blastlib.processing.soft_criterion import (
                    raw_fields_available)
                return raw_fields_available()
        try:
            self._soft_ok, self._soft_reason = status_fn()
        except Exception as exc:          # a broken probe must not kill the GUI
            self._soft_ok, self._soft_reason = False, str(exc)

        crit_line = ttk.Frame(frame)
        crit_line.grid(row=1, column=0, sticky='w', pady=(4, 0))
        ttk.Label(crit_line, text='Convergence criterion:').pack(
            side='left', padx=(0, 8))
        ttk.Radiobutton(crit_line, text='Hard (10 kPa)',
                        variable=self.criterion, value='hard',
                        command=self._sync).pack(side='left', padx=(0, 10))
        self._soft_radio = ttk.Radiobutton(crit_line, text='Soft (tanh, β)',
                                           variable=self.criterion, value='soft',
                                           command=self._sync)
        self._soft_radio.pack(side='left', padx=(0, 6))
        self._beta_spin = ttk.Spinbox(crit_line, textvariable=self.beta,
                                      from_=1, to=20, increment=0.5, width=5)
        self._beta_spin.pack(side='left')

        if not self._soft_ok:
            self._soft_radio.configure(state='disabled')
            Tooltip(self._soft_radio,
                    'Soft criterion unavailable: ' + self._soft_reason)

        self._sync()

    def _sync(self):
        self._spin.configure(
            state='normal' if self.method.get().startswith('p') else 'disabled')
        soft = self.criterion.get() == 'soft' and self._soft_ok
        self._beta_spin.configure(state='normal' if soft else 'disabled')

    def value(self):
        return estimator_value(self.method.get(), self.percentile.get(),
                               self.criterion.get() if self._soft_ok else 'hard',
                               self.beta.get())


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
