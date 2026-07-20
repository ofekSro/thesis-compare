"""Interactive 3D viewer: ground-plane (incident) + building surfaces (OBS).

Usage:
    python view_3d.py

A tkinter dialog lets you choose a configuration, then pyvista shows the
3D scene with a checkbox to toggle between Peak Overpressure and Peak Impulse.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import pyvista as pv
from tkinter import simpledialog


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
WORK_FOLDER = os.path.dirname(os.path.abspath(__file__))
MAT_FOLDER = os.path.join(WORK_FOLDER, 'MAT_files')
OBS_FOLDER = os.path.join(WORK_FOLDER, 'OBS_MAT_files')

FIELD_P = 'Peak Overpressure [kPa]'
FIELD_I = 'Peak Impulse [Pa-s]'

CMAP = 'turbo'


# ---------------------------------------------------------------------------
# Config selector (tkinter)
# ---------------------------------------------------------------------------

def select_configuration():
    """Show a tkinter dialog to pick a config. Returns config name or None."""
    all_configs = sorted(
        f.replace('.npz', '')
        for f in os.listdir(MAT_FOLDER)
        if f.startswith('config_') and f.endswith('.npz')
    )
    if not all_configs:
        messagebox.showerror('Error', f'No .npz files found in {MAT_FOLDER}')
        return None

    obs_configs = set(
        f.replace('.npz', '')
        for f in os.listdir(OBS_FOLDER)
        if f.startswith('config_') and f.endswith('.npz')
    ) if os.path.isdir(OBS_FOLDER) else set()

    selected = [None]

    root = tk.Tk()
    root.title('Select Configuration')
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=15)
    frame.pack(fill='both', expand=True)

    ttk.Label(frame, text='Configuration:', font=('Segoe UI', 10, 'bold')).pack(anchor='w')

    list_frame = ttk.Frame(frame)
    list_frame.pack(fill='both', expand=True, pady=(5, 10))

    scrollbar = ttk.Scrollbar(list_frame)
    scrollbar.pack(side='right', fill='y')

    listbox = tk.Listbox(list_frame, width=50, height=20, font=('Consolas', 9),
                         yscrollcommand=scrollbar.set, selectmode='single')
    listbox.pack(side='left', fill='both', expand=True)
    scrollbar.config(command=listbox.yview)

    for cfg in all_configs:
        marker = '  [+OBS]' if cfg in obs_configs else ''
        listbox.insert('end', cfg + marker)

    for i, cfg in enumerate(all_configs):
        if cfg in obs_configs:
            listbox.itemconfig(i, fg='#006600')

    listbox.select_set(0)

    status_var = tk.StringVar(value=f'{len(all_configs)} configs, {len(obs_configs)} with OBS data')
    ttk.Label(frame, textvariable=status_var, foreground='gray').pack(anchor='w')

    def on_ok():
        sel = listbox.curselection()
        if sel:
            selected[0] = all_configs[sel[0]]
        root.destroy()

    listbox.bind('<Double-Button-1>', lambda e: on_ok())

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill='x', pady=(5, 0))
    ttk.Button(btn_frame, text='View 3D', command=on_ok).pack(side='right', padx=(5, 0))
    ttk.Button(btn_frame, text='Cancel', command=root.destroy).pack(side='right')

    root.bind('<Return>', lambda e: on_ok())
    root.bind('<Escape>', lambda e: root.destroy())

    root.mainloop()
    return selected[0]


# ---------------------------------------------------------------------------
# Build ground-plane meshes (StructuredGrid at Y=0)
# ---------------------------------------------------------------------------

def build_ground_meshes(npz):
    """Create pyvista StructuredGrids for each resolution with P and I data."""
    meshes = []
    for res in ('1', '2', '3'):
        X = npz[f'X{res}']
        Z = npz[f'Z{res}']
        P = npz[f'peakP{res}_orig']
        I = npz[f'impulse{res}_orig']

        # readVTK arrays have shape (nz, nx): rows = z index, cols = x index.
        # pv.StructuredGrid iterates points in Fortran order (first dim fastest),
        # so ravel(order='F') correctly maps P[z_idx, x_idx] to its (x, z) position.
        Y = np.zeros_like(X)
        grid = pv.StructuredGrid(X, Y, Z)
        grid.point_data[FIELD_P] = P.ravel(order='F')
        grid.point_data[FIELD_I] = I.ravel(order='F')
        meshes.append(grid)
    return meshes


# ---------------------------------------------------------------------------
# Build OBS building-surface meshes (PolyData quads)
# ---------------------------------------------------------------------------

def _cell_centroids(points, cells):
    """Compute (n_cells, 3) centroids from points and cell connectivity."""
    return points[cells].mean(axis=1)


def _make_obs_polydata(points, cells, peakP, impulse, keep_mask=None):
    """Build a PolyData from points/cells, optionally filtering by keep_mask."""
    if keep_mask is not None:
        cells = cells[keep_mask]
        if peakP is not None:
            peakP = peakP[keep_mask]
        if impulse is not None:
            impulse = impulse[keep_mask]

    n_cells = cells.shape[0]
    if n_cells == 0:
        return None

    faces = np.empty((n_cells, 5), dtype=np.int64)
    faces[:, 0] = 4
    faces[:, 1:] = cells
    mesh = pv.PolyData(points, faces=faces.ravel())

    if peakP is not None and peakP.size == n_cells:
        mesh.cell_data[FIELD_P] = peakP / 1000.0  # Pa -> kPa
    if impulse is not None and impulse.size == n_cells:
        mesh.cell_data[FIELD_I] = impulse.copy()

    return mesh


def build_obs_meshes(npz):
    """Create pyvista PolyData meshes with smart cut across resolutions.

    Same logic as process_grids.py: coarser grids are cut where finer grids
    already have coverage, so the three resolutions tile without overlap.
    """
    # Load all 3 resolutions
    res_data = {}
    for res in ('1', '2', '3'):
        key_pts = f'points_{res}'
        key_cells = f'cells_{res}'
        if key_pts not in npz or key_cells not in npz:
            continue
        res_data[res] = {
            'points': np.ascontiguousarray(npz[key_pts], dtype=np.float32),
            'cells': np.ascontiguousarray(npz[key_cells], dtype=np.int64),
            'peakP': np.ascontiguousarray(npz.get(f'peakP_{res}', np.array([])), dtype=np.float32),
            'impulse': np.ascontiguousarray(npz.get(f'impulse_{res}', np.array([])), dtype=np.float32),
        }

    if not res_data:
        return []

    meshes = []

    # Res 1 (fine) — keep all cells
    if '1' in res_data:
        d = res_data['1']
        mesh = _make_obs_polydata(d['points'], d['cells'], d['peakP'], d['impulse'])
        if mesh is not None:
            meshes.append(mesh)

        # Compute fine grid X,Z bounds for cutting res 2
        centroids_1 = _cell_centroids(d['points'], d['cells'])
        x_max_1 = centroids_1[:, 0].max()
        z_max_1 = centroids_1[:, 2].max()

    # Res 2 (medium) — cut cells that fall inside res 1's range
    if '2' in res_data:
        d = res_data['2']
        centroids_2 = _cell_centroids(d['points'], d['cells'])

        if '1' in res_data:
            # Keep cells whose centroid is OUTSIDE the fine grid range
            keep_2 = ~((centroids_2[:, 0] <= x_max_1) & (centroids_2[:, 2] <= z_max_1))
        else:
            keep_2 = None

        mesh = _make_obs_polydata(d['points'], d['cells'], d['peakP'], d['impulse'], keep_2)
        if mesh is not None:
            meshes.append(mesh)

        # Compute medium grid bounds for cutting res 3
        x_max_2 = centroids_2[:, 0].max()
        z_max_2 = centroids_2[:, 2].max()

    # Res 3 (coarse) — cut cells that fall inside res 2's range
    if '3' in res_data:
        d = res_data['3']
        centroids_3 = _cell_centroids(d['points'], d['cells'])

        if '2' in res_data:
            keep_3 = ~((centroids_3[:, 0] <= x_max_2) & (centroids_3[:, 2] <= z_max_2))
        else:
            keep_3 = None

        mesh = _make_obs_polydata(d['points'], d['cells'], d['peakP'], d['impulse'], keep_3)
        if mesh is not None:
            meshes.append(mesh)

    return meshes


# ---------------------------------------------------------------------------
# Compute color limits
# ---------------------------------------------------------------------------

def compute_clims(ground_npz, obs_npz):
    """Return (clim_P, clim_I) as [vmin, vmax] lists."""
    all_P = np.concatenate([ground_npz[f'peakP{r}_orig'].ravel() for r in ('1', '2', '3')])
    all_I = np.concatenate([ground_npz[f'impulse{r}_orig'].ravel() for r in ('1', '2', '3')])

    valid_P = all_P[~np.isnan(all_P) & (all_P > 0)]
    valid_I = all_I[~np.isnan(all_I) & (all_I > 0)]

    clim_P = [float(np.percentile(valid_P, 2)), float(np.percentile(valid_P, 98))]
    clim_I = [float(np.percentile(valid_I, 2)), float(np.percentile(valid_I, 98))]

    if obs_npz is not None:
        obs_P = np.concatenate([obs_npz[f'peakP_{r}'].ravel() / 1000.0
                                for r in ('1', '2', '3') if f'peakP_{r}' in obs_npz])
        obs_I = np.concatenate([obs_npz[f'impulse_{r}'].ravel()
                                for r in ('1', '2', '3') if f'impulse_{r}' in obs_npz])
        clim_P[1] = max(clim_P[1], float(np.percentile(obs_P, 98)))
        clim_I[1] = max(clim_I[1], float(np.percentile(obs_I, 98)))

    return clim_P, clim_I


# ---------------------------------------------------------------------------
# 3D Viewer
# ---------------------------------------------------------------------------

def show_3d(config_name, ground_npz, obs_npz=None):
    """Launch pyvista 3D viewer with ground plane + optional building surfaces."""

    # Exaggerate height so buildings are visible (ground is ~100m wide, buildings ~4m tall)
    HEIGHT_SCALE = 5.0

    ground_meshes = build_ground_meshes(ground_npz)
    obs_meshes = build_obs_meshes(obs_npz) if obs_npz is not None else []
    has_obs = len(obs_meshes) > 0

    # Scale the Y axis (height) on all meshes
    for mesh in ground_meshes:
        mesh.points[:, 1] *= HEIGHT_SCALE
    for mesh in obs_meshes:
        mesh.points[:, 1] *= HEIGHT_SCALE

    clim_P, clim_I = compute_clims(ground_npz, obs_npz)

    # ---- Plotter ----
    obs_tag = ' + OBS' if has_obs else ' (no OBS)'
    pl = pv.Plotter(title=f'{config_name}{obs_tag}')

    # State: track current field, clim, and actor references
    state = {
        'field': FIELD_P,
        'clim': list(clim_P),
        'actors': [],
        'grid_actors': [],
        'slider_min': None,
        'slider_max': None,
    }

    def _add_axis_grid():
        """Add X and Z axis lines at 50m steps on the ground plane."""
        for a in state['grid_actors']:
            try:
                pl.remove_actor(a)
            except Exception:
                pass
        state['grid_actors'].clear()

        # Determine range from the coarsest ground mesh
        x_max = ground_npz['X3'].max()
        z_max = ground_npz['Z3'].max()

        ticks = np.arange(0, max(x_max, z_max) + 50, 50)

        for t in ticks:
            if t <= x_max:
                # Z-parallel line at X = t
                line = pv.Line((t, 0, 0), (t, 0, min(t, z_max) if t <= z_max else z_max))
                a = pl.add_mesh(line, color='black', line_width=1, opacity=0.3)
                state['grid_actors'].append(a)
                # Label
                a = pl.add_point_labels(
                    np.array([[t, 0, -8.0]]),
                    [f'{t:.0f}'],
                    font_size=10, text_color='black',
                    point_size=0, shape=None, render_points_as_spheres=False,
                )
                state['grid_actors'].append(a)
            if t <= z_max:
                # X-parallel line at Z = t
                line = pv.Line((0, 0, t), (min(t, x_max) if t <= x_max else x_max, 0, t))
                a = pl.add_mesh(line, color='black', line_width=1, opacity=0.3)
                state['grid_actors'].append(a)
                # Label
                a = pl.add_point_labels(
                    np.array([[-8.0, 0, t]]),
                    [f'{t:.0f}'],
                    font_size=10, text_color='black',
                    point_size=0, shape=None, render_points_as_spheres=False,
                )
                state['grid_actors'].append(a)

        # Axis title labels
        a = pl.add_point_labels(
            np.array([[x_max / 2, 0, -18.0]]),
            ['X [m]'], font_size=14, text_color='black',
            point_size=0, shape=None, bold=True,
        )
        state['grid_actors'].append(a)
        a = pl.add_point_labels(
            np.array([[-18.0, 0, z_max / 2]]),
            ['Z [m]'], font_size=14, text_color='black',
            point_size=0, shape=None, bold=True,
        )
        state['grid_actors'].append(a)

    def add_all_meshes(field):
        """Clear old actors and add all meshes colored by current field + cmap."""
        for a in state['actors']:
            try:
                pl.remove_actor(a)
            except Exception:
                pass
        state['actors'].clear()

        try:
            pl.remove_scalar_bar()
        except Exception:
            pass

        clim = state['clim']
        kwargs = dict(cmap=CMAP, clim=clim, nan_color='lightgray',
                      show_scalar_bar=False)

        for mesh in ground_meshes:
            a = pl.add_mesh(mesh, scalars=field, opacity=0.9, **kwargs)
            state['actors'].append(a)

        for mesh in obs_meshes:
            if field in mesh.cell_data:
                a = pl.add_mesh(mesh, scalars=field, opacity=1.0, **kwargs)
            else:
                a = pl.add_mesh(mesh, color='gray', opacity=0.5)
            state['actors'].append(a)

        pl.add_scalar_bar(title=field, n_labels=5, shadow=True, fmt='%.1f',
                          position_x=0.2, position_y=0.05,
                          width=0.6, height=0.06)

    def _refresh():
        add_all_meshes(state['field'])
        pl.render()

    def toggle_field(flag):
        """Checkbox: flag=True -> Impulse, flag=False -> Overpressure."""
        state['field'] = FIELD_I if flag else FIELD_P
        # Reset clim to auto limits for the new field
        new_clim = list(clim_I if flag else clim_P)
        state['clim'] = new_clim
        # Update slider ranges to match the new field
        g_min = state['global_ranges'][state['field']][0]
        g_max = state['global_ranges'][state['field']][1]
        for widget, val in [(state['slider_min'], new_clim[0]),
                            (state['slider_max'], new_clim[1])]:
            if widget is not None:
                rep = widget.GetRepresentation()
                rep.SetMinimumValue(g_min)
                rep.SetMaximumValue(g_max)
                rep.SetValue(val)
        _refresh()

    def set_vmin(value):
        state['clim'][0] = value
        _refresh()

    def set_vmax(value):
        state['clim'][1] = value
        _refresh()

    _tk_root = tk.Tk()
    _tk_root.withdraw()

    def ask_vmin():
        val = simpledialog.askfloat('Color min', 'Enter min value:',
                                    initialvalue=round(state['clim'][0], 3),
                                    parent=_tk_root)
        if val is not None:
            state['clim'][0] = val
            if state['slider_min'] is not None:
                state['slider_min'].GetRepresentation().SetValue(val)
            _refresh()

    def ask_vmax():
        val = simpledialog.askfloat('Color max', 'Enter max value:',
                                    initialvalue=round(state['clim'][1], 3),
                                    parent=_tk_root)
        if val is not None:
            state['clim'][1] = val
            if state['slider_max'] is not None:
                state['slider_max'].GetRepresentation().SetValue(val)
            _refresh()

    # Initial scene
    add_all_meshes(FIELD_P)
    _add_axis_grid()

    # --- Widgets ---
    # Toggle field (bottom-left)
    pl.add_checkbox_button_widget(
        toggle_field, value=False,
        position=(10, 10), size=30, border_size=2,
        color_on='dodgerblue', color_off='tomato',
    )
    pl.add_text('Overpressure / Impulse',
                position=(50, 12), font_size=9, color='black')

    pl.add_key_event('n', ask_vmin)
    pl.add_key_event('x', ask_vmax)
    pl.add_text('N = type color min  |  X = type color max',
                position=(10, 48), font_size=8, color='gray')

    # Compute overall data range for slider bounds (per field)
    global_min_P = 0.0
    global_max_P = float(np.nanmax([
        np.nanmax(ground_npz[f'peakP{r}_orig']) for r in ('1', '2', '3')
    ] + ([np.nanmax(obs_npz[f'peakP_{r}']) / 1000.0
          for r in ('1', '2', '3') if f'peakP_{r}' in (obs_npz or {})]
         if obs_npz is not None else [])))
    global_min_I = 0.0
    global_max_I = float(np.nanmax([
        np.nanmax(ground_npz[f'impulse{r}_orig']) for r in ('1', '2', '3')
    ] + ([np.nanmax(obs_npz[f'impulse_{r}'])
          for r in ('1', '2', '3') if f'impulse_{r}' in (obs_npz or {})]
         if obs_npz is not None else [])))

    state['global_ranges'] = {
        FIELD_P: (global_min_P, global_max_P),
        FIELD_I: (global_min_I, global_max_I),
    }

    # vmin slider
    state['slider_min'] = pl.add_slider_widget(
        set_vmin,
        rng=[global_min_P, global_max_P],
        value=clim_P[0],
        title='Color min',
        pointa=(0.02, 0.15), pointb=(0.25, 0.15),
        style='modern',
    )
    # vmax slider
    state['slider_max'] = pl.add_slider_widget(
        set_vmax,
        rng=[global_min_P, global_max_P],
        value=clim_P[1],
        title='Color max',
        pointa=(0.02, 0.25), pointb=(0.25, 0.25),
        style='modern',
    )

    pl.add_text(f'{config_name}{obs_tag}',
                position='upper_left', font_size=11, color='black')

    pl.set_background('white')

    # Set camera: look at center from above at an angle
    center_x = 50.0
    center_z = 50.0
    pl.camera_position = [
        (center_x + 150, 120 * HEIGHT_SCALE, center_z + 150),
        (center_x, 0, center_z),
        (0, 1, 0),
    ]

    pl.show()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    config_name = select_configuration()
    if config_name is None:
        print('No configuration selected.')
        return

    print(f'Loading {config_name}...')

    ground_path = os.path.join(MAT_FOLDER, f'{config_name}.npz')
    if not os.path.exists(ground_path):
        print(f'Error: {ground_path} not found.')
        return
    ground_npz = np.load(ground_path, allow_pickle=True)

    obs_path = os.path.join(OBS_FOLDER, f'{config_name}.npz')
    obs_npz = None
    if os.path.exists(obs_path):
        obs_npz = np.load(obs_path)
        print('  OBS data loaded.')
    else:
        print('  No OBS data for this config.')

    show_3d(config_name, ground_npz, obs_npz)


if __name__ == '__main__':
    main()
