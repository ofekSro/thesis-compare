import matplotlib.patches as patches

from blastlib.config.parser import config_parser


def draw_cuboids_gray(ax, config_name):
    """Draw building cuboids with gray fill on a matplotlib axis.

    The rectangles are the true footprints. They used to be drawn 0.5 m
    oversized on every side (bsize + 1.0), which put the grey edge half a
    metre out into the street — enough to make an overlay landing on a facade
    look like it sat inside the building. The masked (NaN) region in the
    processed grids tracks the true footprint to within one grid cell
    (0.15 m), so nothing about the data motivated the padding.

    X and Z are laid out differently on purpose, and that asymmetry is not a
    bug: for det=1 the charge sits mid-street facing a building centred on
    x=0, so the X series is centred on multiples of step while the Z series
    starts at swidth/2. det=2 shifts X by half a step to put the origin at the
    crossing centre, which makes the two axes agree again. Both match the
    exclude_radius geometry in blastlib/geometry.py.
    """
    cfg = config_parser(config_name)
    if cfg is None:
        return

    det = cfg['det']
    bsize = cfg['bsize']
    swidth = cfg['swidth']

    step = bsize + swidth
    half_a = 0.5 * bsize

    offset_x = 0.0 if det == 1 else -0.5 * step

    num_buildings = int(500 / step)

    for i in range(num_buildings):
        x_center = i * step + offset_x
        x0 = x_center - half_a
        x1 = x_center + half_a

        for j in range(num_buildings):
            z0 = 0.5 * swidth + j * step
            z1 = z0 + bsize

            if x1 > 0 and z1 > 0 and x0 < 500 and z0 < 500:
                rect = patches.Rectangle(
                    (x0, z0), bsize, bsize,
                    linewidth=1, edgecolor='k', facecolor=[0.5, 0.5, 0.5]
                )
                ax.add_patch(rect)
