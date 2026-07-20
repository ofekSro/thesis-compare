import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Load data
df = pd.read_csv("convergence_table.csv")

# ---------------------------------------------------------
# Graph 1: Height-effect sensitivity flips sign at the regime
#          boundary (Pi2 = s/W^(1/3) = 1).  This is the regime
#          switch itself -- the SIGN of dZ/d(H/s) -- not the level
#          of Z.  Off-family b=10 (only 2 heights) is excluded.
# ---------------------------------------------------------
plt.figure(figsize=(8, 6))

df_g1 = df[df['BuildingSize'].isin([15, 30])].copy()
df_g1['Z'] = df_g1['RadiusP'] / (df_g1['ChargeWeight'] ** (1 / 3))
df_g1['Hs'] = df_g1['Height'] / df_g1['StreetWidth']

colors = {5: '#c1121f', 8: '#e07a00', 12: '#0353a4', 20: '#2a9d8f'}
markers = {1: 'o', 2: 's'}  # det1 = street, det2 = intersection

# regime quadrants + boundary lines
plt.axvspan(0.38, 1.0, color='#2a9d8f', alpha=0.05)
plt.axvspan(1.0, 6.3, color='#c1121f', alpha=0.04)
plt.axvline(x=1.0, color='k', linestyle='--', linewidth=1.6)
plt.axhline(y=0.0, color='gray', linestyle='-', linewidth=1.0, alpha=0.6)

# slope dZ/d(H/s) within each (Det, BuildingSize, StreetWidth, ChargeWeight)
streets_used = set()
for (det, b, s), grp in df_g1.groupby(['Det', 'BuildingSize', 'StreetWidth']):
    pts = []
    for W, sub in grp.groupby('ChargeWeight'):
        if sub['Hs'].nunique() < 2:
            continue
        slope = np.polyfit(sub['Hs'].values, sub['Z'].values, 1)[0]
        pts.append((s / W ** (1 / 3), slope))
    if not pts:
        continue
    pts.sort(key=lambda p: -p[0])  # order by descending Pi2
    x = [p[0] for p in pts]
    y = [p[1] for p in pts]
    streets_used.add(s)
    plt.plot(x, y, '-', color=colors[s], linewidth=1.3, alpha=0.55)
    plt.scatter(x, y, s=46, color=colors[s], marker=markers[det],
                edgecolor='white', linewidth=0.8, zorder=5)

plt.text(0.55, 2.0, 'Channeling\n(H up -> Z up)\nslope > 0',
         color='#0f6e56', ha='center', fontweight='bold')
plt.text(3.0, -2.4, 'Blocking\n(H up -> Z down)\nslope < 0',
         color='#993c1d', ha='center', fontweight='bold')
plt.text(1.05, 3.0, 'Regime boundary\nPi2 = s/W^(1/3) = 1',
         color='k', ha='left', va='top')

plt.xscale('log')
plt.xlim(0.38, 6.3)
plt.ylim(-3.8, 3.6)
plt.xticks([0.5, 1, 2, 5], ['0.5', '1', '2', '5'])
plt.xlabel('Pi2 = s / W^(1/3)')
plt.ylabel('Height-effect slope, dZ/d(H/s)')
plt.title('Graph 1: Height-Effect Sign Flip at the Regime Boundary\n'
          '(b in {15, 30})')
plt.grid(True, which='both', ls='--', alpha=0.3)

from matplotlib.lines import Line2D
color_handles = [Line2D([], [], marker='o', linestyle='', markerfacecolor=colors[s],
                        markeredgecolor='white', markersize=9, label=f's = {s} m')
                 for s in sorted(streets_used)]
shape_handles = [Line2D([], [], marker='o', linestyle='', color='gray',
                        markersize=9, label='det1 (street)'),
                 Line2D([], [], marker='s', linestyle='', color='gray',
                        markersize=9, label='det2 (intersection)')]
leg1 = plt.legend(handles=color_handles, title='Street width', loc='upper right')
plt.gca().add_artist(leg1)
plt.legend(handles=shape_handles, title='Detonation', loc='lower left')

plt.tight_layout()
plt.savefig('graph1_crossing.png', dpi=150)
plt.close()

# ---------------------------------------------------------
# Graph 2: "Sign Flip" of the height effect.
#          Two building sizes per regime (b=15 solid, b=30 dashed)
#          confirm the trend without crowding the figure.
# ---------------------------------------------------------
plt.figure(figsize=(8, 6))


def g2(b, s, W=500, det=1):
    sub = df[(df['Det'] == det) & (df['BuildingSize'] == b) &
             (df['ChargeWeight'] == W) & (df['StreetWidth'] == s)].copy()
    return sub.sort_values(by='Height')

for b, ls in [(15, '-'), (30, '--')]:
    n = g2(b, 5)
    w = g2(b, 20)
    plt.plot(n['Height'], n['RadiusP'], marker='s', linestyle=ls, color='r', linewidth=2)
    plt.plot(w['Height'], w['RadiusP'], marker='^', linestyle=ls, color='g', linewidth=2)

plt.xlabel('Building Height, H [m]')
plt.ylabel('Convergence Radius, R [m]')
plt.title('Graph 2: Sign Flip of Height Effect\n(det1, W=500kg)')
plt.grid(True, ls="--", alpha=0.7)

from matplotlib.lines import Line2D
regime_handles = [
    Line2D([], [], color='r', marker='s', linewidth=2, label='Narrow s=5 - channeling (H up, R up)'),
    Line2D([], [], color='g', marker='^', linewidth=2, label='Wide s=20 - blocking (H up, R down)'),
]
size_handles = [
    Line2D([], [], color='gray', linestyle='-', linewidth=2, label='b = 15 m'),
    Line2D([], [], color='gray', linestyle='--', linewidth=2, label='b = 30 m'),
]
leg_r = plt.legend(handles=regime_handles, loc='upper left')
plt.gca().add_artist(leg_r)
plt.legend(handles=size_handles, title='Building size', loc='lower right')

plt.tight_layout()
plt.savefig('graph2_sign_flip.png', dpi=150)
plt.close()