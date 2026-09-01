import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from inspection_validator.validator_engine import InspectionValidatorEngine

def test_engine():
    resource_dir = os.path.join(project_root, "resource")
    engine = InspectionValidatorEngine(resource_dir)

    print("=== Testing List Missions ===")
    missions = engine.list_missions()
    print(f"Found {len(missions)} missions:")
    for m in missions:
        print(f"  - {m['folder_name']}: CSV={m['csv_file']}, Media={m['media_count']} (Img:{m['images_count']}, Vid:{m['videos_count']}, Aud:{m['audio_count']})")

    print("\n=== Testing List Templates ===")
    templates = engine.list_templates()
    print(f"Found {len(templates)} template files in resource/path.")
    for t in templates[:5]:
        print(f"  - {t['filename']}: {t['inspection_points_count']} inspections / {t['total_waypoints']} waypoints")

    if missions and templates:
        m_folder = missions[0]['folder_path']
        # Find template with gauge-4 or leakage-14
        t_path = None
        for t in templates:
            if "final_dry_full" in t["filename"] or "new-dry-full" in t["filename"]:
                t_path = t["full_path"]
                break
        if not t_path:
            t_path = templates[0]["full_path"]

        print(f"\n=== Testing Validation Audit ({missions[0]['folder_name']} vs {os.path.basename(t_path)}) ===")
        report = engine.validate(m_folder, t_path)
        print("Summary Result:", report["summary"])

if __name__ == "__main__":
    test_engine()
