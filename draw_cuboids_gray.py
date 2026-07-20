import re
import matplotlib.patches as patches


def draw_cuboids_gray(ax, config_name):
    """Draw building cuboids with gray fill on a matplotlib axis.

    Same as draw_cuboids but with FaceColor = [0.5, 0.5, 0.5] (gray).
    Equivalent to REFERENCES/pi_criterion_check/draw_cuboids_gray.m
    """
    m = re.search(r'det(\d+)_b(\d+)_s(\d+)_h(\d+)_w(\d+)', config_name)
    if not m:
        return

    det = int(m.group(1))
    bsize = int(m.group(2))
    swidth = int(m.group(3))

    step = bsize + swidth
    half_a = 0.5 * bsize

    offset_x = 0.0 if det == 1 else -0.5 * step

    num_buildings = int(500 / step)

    for i in range(num_buildings):
        x_center = i * step + offset_x
        x0 = x_center - half_a - 0.5
        x1 = x_center + half_a + 0.5

        for j in range(num_buildings):
            z0 = 0.5 * swidth + j * step - 0.5
            z1 = z0 + bsize + 1.0

            if x1 > 0 and z1 > 0 and x0 < 500 and z0 < 500:
                rect = patches.Rectangle(
                    (x0, z0), bsize + 1.0, bsize + 1.0,
                    linewidth=1, edgecolor='k', facecolor=[0.5, 0.5, 0.5]
                )
                ax.add_patch(rect)
