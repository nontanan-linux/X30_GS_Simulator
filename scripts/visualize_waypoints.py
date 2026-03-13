import os
from docx import Document

# Configuration
DOCX_FILE = 'nestle_cat_waypoints_updated.docx'
NAME_COL = 1
ZONE_COL = 2
FUNC_COL = 3
INSP_COL = 5

def main():
    if not os.path.exists(DOCX_FILE):
        print(f"Error: {DOCX_FILE} not found.")
        return

    print(f"Loading {DOCX_FILE}...")
    doc = Document(DOCX_FILE)
    
    waypoint_data = []
    
    # Iterate through tables in the document
    for table in doc.tables:
        for row in table.rows[1:]: # Skip header
            if len(row.cells) > max(NAME_COL, ZONE_COL, FUNC_COL, INSP_COL):
                name = row.cells[NAME_COL].text.strip()
                zone = row.cells[ZONE_COL].text.strip()
                func = row.cells[FUNC_COL].text.strip()
                insp = row.cells[INSP_COL].text.strip()
                
                if name:
                    waypoint_data.append({
                        'name': name,
                        'zone': zone if zone else "-",
                        'function': func if func else "-",
                        'inspection': insp if insp else "-"
                    })

    if not waypoint_data:
        print("No waypoint data found in the document.")
        return

    # Sort by zone (primary), function (secondary), and inspection (tertiary)
    waypoint_data.sort(key=lambda x: (x['zone'], x['function'], x['inspection']))

    # Print Table
    width_name = 35
    width_zone = 10
    width_func = 15
    width_insp = 25
    
    table_width = width_name + width_zone + width_func + width_insp + 13
    
    print("\n" + "=" * table_width)
    print(f"| {'Point Name':<{width_name}} | {'Zone':<{width_zone}} | {'Function':<{width_func}} | {'Inspection':<{width_insp}} |")
    print("|" + "-" * (width_name + 2) + "|" + "-" * (width_zone + 2) + "|" + "-" * (width_func + 2) + "|" + "-" * (width_insp + 2) + "|")
    
    current_key = None
    for wp in waypoint_data:
        # Add a separator line when zone or function changes for better readability
        new_key = (wp['zone'], wp['function'])
        if current_key is not None and new_key != current_key:
            print("|" + "-" * (width_name + 2) + "+" + "-" * (width_zone + 2) + "+" + "-" * (width_func + 2) + "+" + "-" * (width_insp + 2) + "|")
        
        current_key = new_key
        
        # Truncate strings if they are too long for the table
        display_name = (wp['name'][:width_name-3] + '...') if len(wp['name']) > width_name else wp['name']
        display_insp = (wp['inspection'][:width_insp-3] + '...') if len(wp['inspection']) > width_insp else wp['inspection']
        
        print(f"| {display_name:<{width_name}} | {wp['zone']:<{width_zone}} | {wp['function']:<{width_func}} | {display_insp:<{width_insp}} |")
        
    print("=" * table_width)
    print(f"Total points displayed: {len(waypoint_data)}\n")

if __name__ == "__main__":
    main()
