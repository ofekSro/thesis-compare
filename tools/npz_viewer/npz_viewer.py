"""Minimal viewer for raw_npz / processed_npz files: pick a key, see it.

Usage:
    python tools\\npz_viewer\\npz_viewer.py [file.npz]

Read-only. Writes nothing.
"""
import sys
import tkinter as tk
from tkinter import filedialog

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.colors import LogNorm
from matplotlib.figure import Figure

MAX_LINE_POINTS = 20000  # decimate long 1-D arrays (peakP_all has ~1e6) for display only


def main(path=None):
    """Open the viewer window, optionally loading `path` (an .npz file)."""
    root = tk.Tk()
    root.title("NPZ viewer")
    state = {"data": None}

    top = tk.Frame(root)
    top.pack(side=tk.TOP, fill=tk.X)
    log_var = tk.BooleanVar(value=False)
    file_lbl = tk.Label(top, text="(no file)", anchor="w")

    left = tk.Frame(root)
    left.pack(side=tk.LEFT, fill=tk.Y)
    keys = tk.Listbox(left, width=45, exportselection=False)
    keys.pack(fill=tk.Y, expand=True)

    fig = Figure(figsize=(7, 6))
    canvas = FigureCanvasTkAgg(fig, master=root)
    NavigationToolbar2Tk(canvas, root).update()
    canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    def load(p):
        state["data"] = np.load(p, allow_pickle=True)
        file_lbl.config(text=p)
        keys.delete(0, tk.END)
        for k in state["data"].files:
            a = state["data"][k]
            keys.insert(tk.END, f"{k}  {a.dtype}  {a.shape}")

    def show(_event=None):
        sel = keys.curselection()
        if not sel or state["data"] is None:
            return
        k = state["data"].files[sel[0]]
        a = np.asarray(state["data"][k])
        fig.clf()
        ax = fig.add_subplot(111)
        if a.ndim == 2:
            a = a.astype(float)
            norm = None
            if log_var.get():
                pos = a[np.isfinite(a) & (a > 0)]
                if pos.size:
                    norm = LogNorm(vmin=pos.min(), vmax=pos.max())
            im = ax.imshow(a, origin="lower", norm=norm, cmap="viridis")
            fig.colorbar(im, ax=ax)
            ax.set_title(f"{k}  min={np.nanmin(a):.4g}  max={np.nanmax(a):.4g}")
        elif a.ndim == 1:
            step = max(1, a.size // MAX_LINE_POINTS)
            ax.plot(np.arange(0, a.size, step), a[::step], lw=0.8)
            if log_var.get():
                ax.set_yscale("log")
            ax.set_title(f"{k}  (n={a.size}, every {step})")
        else:
            ax.axis("off")
            ax.text(0.5, 0.5, f"{k} = {a}", ha="center", va="center", fontsize=14)
        canvas.draw()

    def open_file():
        p = filedialog.askopenfilename(filetypes=[("NPZ", "*.npz"), ("All", "*.*")])
        if p:
            load(p)

    tk.Button(top, text="Open", command=open_file).pack(side=tk.LEFT)
    tk.Checkbutton(top, text="log scale", variable=log_var, command=show).pack(side=tk.LEFT)
    file_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
    keys.bind("<<ListboxSelect>>", show)

    if path:
        load(path)
    root.mainloop()


def cli():
    main(sys.argv[1] if len(sys.argv) > 1 else None)


if __name__ == "__main__":
    cli()
