import re


def config_parser(config_name):
    """Extract parameters from config name string.

    Example: 'config_det1_b15_s5_h10_w500'
    Returns dict with: det, bsize, swidth, height, weight, axis_limit
    Returns None if parsing fails.
    Equivalent to REFERENCES/pi_criterion_check/config_parser.m
    """
    cfg = {}

    # Extract det and w
    m = re.search(r'det(\d+).*_w(\d+)', config_name)
    if not m:
        return None
    cfg['det'] = int(m.group(1))
    cfg['weight'] = int(m.group(2))

    # Extract b and s
    m_bs = re.search(r'b(\d+)_s(\d+)', config_name)
    if not m_bs:
        return None
    cfg['bsize'] = int(m_bs.group(1))
    cfg['swidth'] = int(m_bs.group(2))

    # Extract h
    m_h = re.search(r'h(\d+)', config_name)
    cfg['height'] = int(m_h.group(1)) if m_h else 0

    # Axis limit based on charge weight (same as MATLAB)
    if cfg['weight'] == 50:
        cfg['axis_limit'] = 100
    elif cfg['weight'] == 500:
        cfg['axis_limit'] = 150
    else:
        cfg['axis_limit'] = 200

    return cfg
