import pandas as pd
import os

def print_convergence_formulas(csv_path):
    if not os.path.exists(csv_path):
        return
    df = pd.read_csv(csv_path)
    print("="*70)
    print(" BEST CONVERGENCE RADIUS FORMULAS    R = W^(1/3) * Z")
    print(" RadiusP: Z = C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)")
    print("                + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1)")
    print(" RadiusI: Z = A * Pi^(k*ln(W^1/3/s)),  Pi = H/(s*rho)")
    print("="*70)
    for target in ['RadiusP', 'RadiusI']:
        print(f"\n--- {target} ---")
        subset = df[df['Target'] == target]
        for _, row in subset.iterrows():
            print(f"  {row['Location']}:")
            if row['Formula'] == 'log':
                print(f"    Z = {row['A']:.4f} * Pi^({row['k']:+.4f}*ln(W^1/3/s))")
            else:
                print(f"    Z = {row['C0']:+.4f} {row['C1_sW13']:+.4f}*(s/W^1/3)"
                      f" {row['C2_switch']:+.4f}*rho*(s/W^1/3 - {row['a_thresh']:g})"
                      f" {row['C3_canyon']:+.4f}*sqrt(rho)*(H/s)*(W^1/3/s - 1)")
            print("    R = W^(1/3) * Z")

def print_z_urban_formulas(csv_path):
    if not os.path.exists(csv_path):
        return
    df = pd.read_csv(csv_path)
    det_map = {1: 'Street (det=1)', 2: 'Intersection (det=2)'}
    print("\n" + "="*70)
    print(" BEST Z_URBAN FORMULAS    MaxR = W^(1/3) * Z_urban")
    print(" Z_urban = C * Z_free^m * rho^p * (H/s)^q * (s/W^(1/3))^r")
    print(" R_urban = W^(1/3) * Z_urban  (canonical -- not separately fitted)")
    print(" Validity: Z_free >= Zf_min (1 pressure, 2 impulse)")
    print(" Physical closure: clip predictions to Z_free <= Z_urban <= Z_conv")
    print(" (Z_conv from the convergence formulas); identity beyond Z_conv.")
    print(" Groups: by det only (2 formulas per target)")
    print("="*70)
    for _, row in df.iterrows():
        print(f"\n  {det_map.get(int(row['Det']), str(row['Det']))} / {row['Target']}:")
        print(f"    Z_urban = {row['C']:.4f} * Z_free^{row['m']:.4f}"
              f" * rho^{row['p_rho']:+.4f} * (H/s)^{row['q_HoverS']:+.4f}"
              f" * (s/W^1/3)^{row['r_sW13']:+.4f}")
        print(f"    MaxR = W^(1/3) * Z_urban    [Z_free >= {row['Zf_min']:g}]")

if __name__ == "__main__":
    work_dir = os.path.dirname(os.path.abspath(__file__))
    print_convergence_formulas(os.path.join(work_dir, 'best_convergence_coefficients.csv'))
    print_z_urban_formulas(os.path.join(work_dir, 'best_z_urban_coefficients.csv'))
