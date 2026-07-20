"""
Z_surface_3d.py — 3D surfaces of the pressure convergence radius Z_P
as a function of any two of the three geometric Pi groups, with the
third held fixed.

    Z_P = C0 + C1*Pi2 + C2*rho*(Pi2 - a) + C3*sqrt(rho)*(H/s)*(1/Pi2 - 1)
    R_P = W^(1/3) * Z_P

Usage:
    python Z_surface_3d.py
    -> it asks which variable to fix (pi2 / rho / hs), its value, and det (1/2).

The fixed variable is held constant; the other two become the X, Y axes.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm

# production-fit coefficients (use for thesis)
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


def make(fix, value, det):
    c = COEF[det]
    xg, xlab, yg, ylab, zf = AXES[fix]
    X, Y = np.meshgrid(xg, yg)
    Z = zf(X, Y, value, c)

    fig = plt.figure(figsize=(10, 7.5))
    ax = fig.add_subplot(111, projection='3d')
    surf = ax.plot_surface(X, Y, Z, cmap=cm.viridis, linewidth=0,
                           antialiased=True, alpha=0.95, rcount=80, ccount=80)

    # mark the regime boundary Pi2 = 1 when it lies on an axis
    if fix == 'rho':          # X is Pi2 -> vertical line at X=1
        yb = yg
        zb = zf(np.ones_like(yb), yb, value, c)
        ax.plot(np.ones_like(yb), yb, zb, color='red', lw=2.5, zorder=10)
    elif fix == 'hs':         # X is Pi2 -> vertical line at X=1
        yb = yg
        zb = zf(np.ones_like(yb), yb, value, c)
        ax.plot(np.ones_like(yb), yb, zb, color='red', lw=2.5, zorder=10)
    # when fix == 'pi2' the boundary is the whole slice value==1 (no line)

    det_name = 'street' if det == 1 else 'intersection'
    ax.set_xlabel('\n' + xlab, fontsize=11)
    ax.set_ylabel('\n' + ylab, fontsize=11)
    ax.set_zlabel('\nZ$_P$ = R$_P$ / W$^{1/3}$', fontsize=11)
    ax.set_title(f'Pressure Z$_P$  (det{det} {det_name}, {FIXLABEL[fix]} = {value})',
                 fontsize=12, fontweight='bold')
    fig.colorbar(surf, ax=ax, shrink=0.6, pad=0.10).set_label('Z$_P$')
    ax.view_init(elev=22, azim=-128)
    fig.tight_layout()

    out = f'Z_surface_fix_{fix}_det{det}.png'
    fig.savefig(out, dpi=150, bbox_inches='tight')
    print('saved', out, '| Z range', round(float(Z.min()), 2), '-', round(float(Z.max()), 2))


def ask_choice(prompt, options):
    while True:
        ans = input(prompt).strip().lower()
        if ans in options:
            return ans
        print('  invalid — choose one of:', ', '.join(options))


def ask_float(prompt):
    while True:
        try:
            return float(input(prompt).strip())
        except ValueError:
            print('  invalid — enter a number')


if __name__ == '__main__':
    print('3D surface of pressure Z_P — fix one variable, plot the other two.\n')

    fix = ask_choice('Which variable to FIX? [pi2 / rho / hs]: ',
                     ['pi2', 'rho', 'hs'])

    hints = {'pi2': '(e.g. 0.63 = regime B, 2.52 = regime A)',
             'rho': '(0.18 - 0.74; e.g. 0.56)',
             'hs':  '(0.2 - 4.8; e.g. 2.0)'}
    value = ask_float(f'Value for {FIXLABEL[fix]} {hints[fix]}: ')

    det = int(ask_choice('Detonation type? [1 = street / 2 = intersection]: ',
                         ['1', '2']))

    make(fix, value, det)