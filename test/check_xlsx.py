import pandas as pd
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
nestle_cat_dir = os.path.dirname(project_root)

files = [
    os.path.join(nestle_cat_dir, 'nestle_cat_waypoints.xlsx'),
    os.path.join(nestle_cat_dir, 'nestle_cat_waypoints_updated.xlsx')
]

for file in files:
    if os.path.exists(file):
        print(f"Checking {file}...")
        try:
            df = pd.read_excel(file, sheet_name=None)
            for sheet_name, sheet_df in df.items():
                mask = sheet_df.astype(str).apply(lambda x: x.str.contains('low_vibration', case=False)).any(axis=1)
                matches = sheet_df[mask]
                if not matches.empty:
                    print(f"  Found matches in sheet '{sheet_name}':")
                    print(matches)
        except Exception as e:
            print(f"  Error reading {file}: {e}")
    else:
        print(f"{file} does not exist.")
