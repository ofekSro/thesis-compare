"""3D surfaces of the pressure convergence radius Z_P as a function of any
two of the three geometric Pi groups, with the third held fixed.

    Z_P = C0 + C1*Pi2 + C2*rho*(Pi2 - a) + C3*sqrt(rho)*(H/s)*(1/Pi2 - 1)
    R_P = W^(1/3) * Z_P

Usage:
    python tools\\z_surface_3d\\z_surface_3d.py                    # prompts
    python tools\\z_surface_3d\\z_surface_3d.py --fix rho --value 0.56 --det 1

The fixed variable is held constant; the other two become the X, Y axes.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import cm

from blastlib import paths

# HARDCODED production-fit coefficients (from the Jun 2026 regression run).
# These are NOT read from disk — if you re-run the regression, these values
# go stale silently. Compare against
# outputs/tables/final_production_convergence_coefficients.csv (rows with
# Target=RadiusP: C0, C1_sW13, C2_switch, C3_canyon, a_thresh) and update
# this dict by hand if they differ.
COEF = {
    1: dict(C0=7.778,  C1=-0.576, C2=2.298, C3=0.576, a=1),  # street
    2: dict(C0=10.060, C1=-1.157, C2=2.185, C3=0.710, a=2),  # intersection
}

# axis sampling ranges (match dataset coverage)
PI2 = np.linspace(0.4, 4.0, 120)
RHO = np.linspace(0.18, 0.74, 120)
HS  = np.linspace(0.2, 4.8, 120)


def Zp(pi2, rho, hs, c):
    return (c['C0'] + c['C1'] * pi2 + c['C2'] * rho * (pi2 - c['a'])
            + c['C3'] * np.sqrt(rho) * hs * (1.0 / pi2 - 1.0))


# (fixed-variable) -> (x grid, x label, y grid, y label, build z(X,Y,fixed))
AXES = {
    'pi2': (RHO, 'ρ = b²/(b+s)²', HS, 'H / s',
            lambda X, Y, v, c: Zp(v, X, Y, c)),
    'rho': (PI2, 'Π₂ = s / W$^{1/3}$', HS, 'H / s',
            lambda X, Y, v, c: Zp(X, v, Y, c)),
    'hs':  (PI2, 'Π₂ = s / W$^{1/3}$', RHO, 'ρ = b²/(b+s)²',
            lambda X, Y, v, c: Zp(X, Y, v, c)),
}
FIXLABEL = {'pi2': 'Π₂', 'rho': 'ρ', 'hs': 'H/s'}
HINTS = {'pi2': '(e.g. 0.63 = regime B, 2.52 = regime A)',
         'rho': '(0.18 - 0.74; e.g. 0.56)',
         'hs':  '(0.2 - 4.8; e.g. 2.0)'}


def main(fix, value, det, *, out_dir=None, progress=print):
    """Render one Z_P surface. Returns the written PNG path."""
    out_dir = paths.ensure_dir(paths.resolve(out_dir, paths.FIGURES_DIR / 'z_surface'))

    c = COEF[det]
    xg, xlab, yg, ylab, zf = AXES[fix]
    X, Y = np.meshgrid(xg, yg)
    Z = zf(X, Y, value, c)

    fig = plt.figure(figsize=(10, 7.5))
    ax = fig.add_subplot(111, projection='3d')
    surf = ax.plot_surface(X, Y, Z, cmap=cm.viridis, linewidth=0,
                           antialiased=True, alpha=0.95, rcount=80, ccount=80)

    # mark the regime boundary Pi2 = 1 when it lies on an axis
    # (when fix == 'pi2' the boundary is the whole slice value==1, so no line)
    if fix in ('rho', 'hs'):      # X is Pi2 -> vertical line at X=1
        yb = yg
        zb = zf(np.ones_like(yb), yb, value, c)
        ax.plot(np.ones_like(yb), yb, zb, color='red', lw=2.5, zorder=10)

    det_name = 'street' if det == 1 else 'intersection'
    ax.set_xlabel('\n' + xlab, fontsize=11)
    ax.set_ylabel('\n' + ylab, fontsize=11)
    ax.set_zlabel('\nZ$_P$ = R$_P$ / W$^{1/3}$', fontsize=11)
    ax.set_title(f'Pressure Z$_P$  (det{det} {det_name}, {FIXLABEL[fix]} = {value})',
                 fontsize=12, fontweight='bold')
    fig.colorbar(surf, ax=ax, shrink=0.6, pad=0.10).set_label('Z$_P$')
    ax.view_init(elev=22, azim=-128)
    fig.tight_layout()

    out = out_dir / f'Z_surface_fix_{fix}_det{det}.png'
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    progress(f'saved {out} | Z range {round(float(Z.min()), 2)} - {round(float(Z.max()), 2)}')
    return out


def _ask_choice(prompt, options):
    """Ask until a valid option is given; return None if stdin is unusable."""
    while True:
        try:
            ans = input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if ans in options:
            return ans
        print('  invalid — choose one of:', ', '.join(options))


def _ask_float(prompt):
    """Ask until a number is given; return None if stdin is unusable."""
    while True:
        try:
            return float(input(prompt).strip())
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        except ValueError:
            print('  invalid — enter a number')


def cli(argv=None):
    p = argparse.ArgumentParser(description='3D surface of pressure Z_P.')
    p.add_argument('--fix', choices=['pi2', 'rho', 'hs'], default=None,
                   help='Which variable to hold fixed.')
    p.add_argument('--value', type=float, default=None,
                   help='Value of the fixed variable.')
    p.add_argument('--det', type=int, choices=[1, 2], default=None,
                   help='1 = street, 2 = intersection.')
    p.add_argument('--out-dir', default=None, help='Output folder for the figure.')
    args = p.parse_args(argv)

    # isatty() alone is not reliable — some non-interactive launchers report a
    # tty but deliver EOF on the first read, so the ask helpers return None.
    interactive = sys.stdin is not None and sys.stdin.isatty()

    fix, value, det = args.fix, args.value, args.det

    if fix is None:
        if interactive:
            print('3D surface of pressure Z_P — fix one variable, plot the other two.\n')
            fix = _ask_choice('Which variable to FIX? [pi2 / rho / hs]: ',
                              ['pi2', 'rho', 'hs'])
        if fix is None:
            p.error('--fix is required when running non-interactively.')
    if value is None:
        if interactive:
            value = _ask_float(f'Value for {FIXLABEL[fix]} {HINTS[fix]}: ')
        if value is None:
            p.error('--value is required when running non-interactively.')
    if det is None:
        if interactive:
            choice = _ask_choice('Detonation type? [1 = street / 2 = intersection]: ',
                                 ['1', '2'])
            det = int(choice) if choice is not None else None
        if det is None:
            p.error('--det is required when running non-interactively.')

    return main(fix, value, det, out_dir=args.out_dir)


if __name__ == '__main__':
    cli()
