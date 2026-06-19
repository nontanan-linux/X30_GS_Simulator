import os
import json
import re

def print_table(headers, rows, title=None):
    """Prints a styled grid table using basic strings."""
    if title:
        print(f"\n{title}")
    
    # Determine column widths
    widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))
    
    # Build the separator line
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    
    # Print header
    print(sep)
    header_str = "|" + "|".join(f" {str(headers[i]):<{widths[i]}} " for i in range(len(headers))) + "|"
    print(header_str)
    print(sep.replace("-", "="))
    
    # Print rows
    for row in rows:
        row_str = "|" + "|".join(f" {str(row[i]):<{widths[i]}} " for i in range(len(row))) + "|"
        print(row_str)
    
    print(sep)

def check_dry_zone_images():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    json_path = os.path.join(project_root, "resource", "path", "dry_zone.json")
    img_dir = os.path.join(project_root, "resource", "maps", "Dry_zone")
    
    if not os.path.exists(json_path):
        print(f"Error: JSON file not found at {json_path}")
        return
    if not os.path.exists(img_dir):
        print(f"Error: Image directory not found at {img_dir}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # Categories to check
    categories = ["leaked", "thermal", "vibration", "loto", "gauge", "asset"]
    
    # Extract inspection points from JSON
    inspection_wps = []
    for wp in data:
        # Check Node_info or Inspection field
        node_info = wp.get('Node_info', '')
        inspection_type = wp.get('Inspection', wp.get('inspection', ''))
        
        if inspection_type and any(cat in node_info.lower() for cat in categories):
            inspection_wps.append(node_info)
            
    images = [img for img in os.listdir(img_dir) if img.endswith('.png')]
    
    matches = {} # wp -> img
    missing = []
    
    for wp in inspection_wps:
        # Extract type and number from Node_info
        # e.g., dry-leaked-14 -> leaked-14
        match = re.search(rf"({'|'.join(categories)})[-_]*(\d+)", wp.lower())
        if not match:
            missing.append((wp, "Could not parse type/number"))
            continue
            
        wp_type = match.group(1)
        wp_num = int(match.group(2))
        
        # Look for a matching image
        found = False
        for img in images:
            clean_img = img.lower().replace('--', '-')
            
            # Pattern: type and number (allowing leading zeros and suffixes like 'low')
            # e.g., loto-07 should match loto-7
            # e.g., leaked-25low should match leaked-25
            img_pattern = rf"{wp_type}[-_]*0*{wp_num}"
            if re.search(img_pattern, clean_img):
                matches[wp] = img
                found = True
                break
        
        if not found:
            missing.append((wp, f"No image found for {wp_type}-{wp_num}"))
            
    # Prepare console table
    headers = ["Waypoint (Node_info)", "Status", "Image File"]
    rows = []
    
    # Sort waypoints for better readability in table
    inspection_wps.sort(key=lambda x: (re.search(r'([a-z]+)', x).group(1) if re.search(r'([a-z]+)', x) else "", 
                                     int(re.search(r'(\d+)', x).group(1)) if re.search(r'(\d+)', x) else 0))

    for wp in inspection_wps:
        img = matches.get(wp)
        status = "MATCH" if img else "MISSING"
        img_disp = img if img else "---"
        rows.append([wp, status, img_disp])
    
    print_table(headers, rows, title="DRY ZONE IMAGE MATCH AUDIT")

    # Generate Markdown table for artifact
    markdown_lines = [
        "# Dry Zone Image Match Audit",
        "",
        "This table shows the match status for every inspection waypoint in `dry_zone.json` against the files in `resource/maps/Dry_zone/`.",
        "",
        "| Waypoint (`Node_info`) | Status | Matching Image File |",
        "| :--- | :--- | :--- |"
    ]
    for row in rows:
        status_md = "✅ MATCH" if row[1] == "MATCH" else "❌ MISSING"
        img_md = f"`{row[2]}`" if row[2] != "---" else "-"
        markdown_lines.append(f"| {row[0]} | {status_md} | {img_md} |")

    # Unused images section in Markdown
    markdown_lines.extend([
        "",
        "## Unused Inspection Images",
        "",
        "| Image File | Potential Issue |",
        "| :--- | :--- |"
    ])
    
    used_images = set(matches.values())
    unused = sorted([img for img in images if img not in used_images])
    inspection_unused = [img for img in unused if any(cat in img.lower() for cat in categories)]
    
    for img in inspection_unused:
        markdown_lines.append(f"| `{img}` | Unused in JSON |")

    # Write to artifact
    artifact_path = os.path.join(project_root, "dry_zone_image_audit.md")
    with open(artifact_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(markdown_lines))
    
    print(f"\nAudit table also written to {artifact_path}")
            
if __name__ == "__main__":
    check_dry_zone_images()
