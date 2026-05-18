import json
import os
import glob
import ast
import csv
from collections import Counter
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

# Layout Constants
SLIDE_WIDTH = 13.333
SLIDE_HEIGHT = 7.5

# Colors
BG_COLOR = RGBColor(10, 15, 30)
CARD_BG = RGBColor(25, 35, 55)
ACCENT_BLUE = RGBColor(99, 102, 241)
TEXT_PRIMARY = RGBColor(255, 255, 255)
TEXT_SECONDARY = RGBColor(160, 174, 192)

MISSION_DIR = '/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/mission-404'

def find_images(point_name, inspection_type):
    suffixes = []
    if inspection_type == 'thermal_inspection':
        suffixes = ['_raw_rgb_image.jpg', '_thermal_map.jpg']
    elif inspection_type == 'gauge_inspection':
        suffixes = ['_preprocessed_rgb_image.jpg', '_processed_rgb_image.jpg']
    elif inspection_type in ['leakage_inspection', 'vibration_inspection']:
        suffixes = ['_spect_photo.jpg', '_voiceprint_photo.jpg', '_soundmap_photo.jpg']
    elif inspection_type in ['asset_inspection', 'loto_inspection']:
        suffixes = ['_processed_rgb_image.jpg']
    
    found_files = []
    for suffix in suffixes:
        pattern = os.path.join(MISSION_DIR, f'*{point_name}*{suffix}')
        matches = glob.glob(pattern)
        if matches:
            found_files.append(matches[0]) # Take first match
            
    return found_files

def add_slide(prs, point, index, total):
    blank_slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank_slide_layout)
    
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = BG_COLOR
    
    def add_text(left, top, width, height, text, font_size=12, bold=False, color=TEXT_PRIMARY, alignment=PP_ALIGN.LEFT):
        txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = txBox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = text
        p.alignment = alignment
        p.font.size = Pt(font_size)
        p.font.bold = bold
        p.font.color.rgb = color
        p.font.name = 'Arial'
        return txBox

    def add_card(left, top, width, height, label, value):
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
        shape.fill.solid()
        shape.fill.fore_color.rgb = CARD_BG
        shape.line.visible = False
        add_text(left + 0.1, top + 0.1, width - 0.2, 0.3, label, font_size=9, color=TEXT_SECONDARY)
        add_text(left + 0.1, top + 0.35, width - 0.2, 0.4, value, font_size=14, bold=True)

    name = point.get('Node_info', 'N/A')
    raw_type = point.get('Inspection', 'General')
    type_display = raw_type.replace('_', ' ').title()
    zone = point.get('Zone', 'N/A')
    floor = point.get('MapName', 'N/A').replace('_', ' ').title()

    # 1. Main Title
    seq_num = f"{index+1:03d}"
    title_text = f"Inspection Point Details - [{seq_num}]"
    add_text(0.5, 0.4, 11.0, 0.8, title_text, font_size=36, bold=True)
    
    # 2. Logo (Flush Top-Right)
    logo_path = '/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/gensurv-logo.jpg'
    if os.path.exists(logo_path):
        logo_h = 0.6
        slide.shapes.add_picture(logo_path, Inches(12.733), Inches(0.0), height=Inches(logo_h))
    
    # 3. Metadata Row (Compacted)
    card_y = 1.3
    card_h = 1.0
    spacing = 0.1
    
    # New Widths
    w_name = 2.4
    w_type = 2.4
    w_loc = 2.0  # Combined Zone & Floor
    
    add_card(0.5, card_y, w_name, card_h, "Inspection Point Name", name)
    add_card(0.5 + w_name + spacing, card_y, w_type, card_h, "Inspection Type", type_display)
    
    # Combined Zone & Floor Card
    loc_x = 0.5 + w_name + w_type + spacing*2
    shape_loc = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(loc_x), Inches(card_y), Inches(w_loc), Inches(card_h))
    shape_loc.fill.solid()
    shape_loc.fill.fore_color.rgb = CARD_BG
    shape_loc.line.visible = False
    add_text(loc_x + 0.1, card_y + 0.05, w_loc - 0.2, 0.3, "Zone & Floor", font_size=9, color=TEXT_SECONDARY)
    add_text(loc_x + 0.1, card_y + 0.3, w_loc - 0.2, 0.3, f"Zone: {zone}", font_size=11, bold=True)
    add_text(loc_x + 0.1, card_y + 0.6, w_loc - 0.2, 0.3, f"Floor: {floor}", font_size=11, bold=True)
    
    # Expanded Result Status Card
    status_x = loc_x + w_loc + spacing
    w_status = (SLIDE_WIDTH - 0.5) - status_x
    
    threshold = point.get('Threshold', 'N/A')
    
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(status_x), Inches(card_y), Inches(w_status), Inches(card_h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = CARD_BG
    shape.line.visible = False
    add_text(status_x + 0.1, card_y + 0.05, w_status - 0.2, 0.3, "Result Status", font_size=9, color=TEXT_SECONDARY)
    
    # Get Data from CSV if available
    notif = notifications.get(name, {})
    csv_res = notif.get('result_dict', {})
    csv_level = notif.get('notification_level', 'N/A').title()
    
    if raw_type == 'thermal_inspection':
        min_temp = csv_res.get('min_temperature', 'N/A')
        max_temp = csv_res.get('max_temperature', 'N/A')
        add_text(status_x + 0.1, card_y + 0.25, w_status - 0.2, 0.25, f"Notification Level: {csv_level}", font_size=10, bold=True)
        add_text(status_x + 0.1, card_y + 0.50, w_status - 0.2, 0.25, f"Threshold: {threshold}", font_size=10, bold=True)
        add_text(status_x + 0.1, card_y + 0.75, w_status - 0.2, 0.25, f"Temperature-Range: {min_temp}-{max_temp}", font_size=10, bold=True)
    elif raw_type == 'leakage_inspection':
        is_leak = csv_res.get('is_leak', 'N/A')
        add_text(status_x + 0.1, card_y + 0.25, w_status - 0.2, 0.25, f"Is Leak: {is_leak}", font_size=10, bold=True)
        add_text(status_x + 0.1, card_y + 0.50, w_status - 0.2, 0.25, f"Notification Level: {csv_level}", font_size=10, bold=True)
        add_text(status_x + 0.1, card_y + 0.75, w_status - 0.2, 0.25, "Frequency Range:", font_size=10, bold=True)
    elif raw_type == 'vibration_inspection':
        k_thresh = point.get('Kurtosis_threshold', 'N/A')
        p_thresh = point.get('Peak_threshold', 'N/A')
        k_val = csv_res.get('kurtosis', 'N/A')
        p_val = csv_res.get('peak_factor', 'N/A')
        add_text(status_x + 0.1, card_y + 0.25, w_status - 0.2, 0.2, f"Notification Level: {csv_level}", font_size=9, bold=True)
        add_text(status_x + 0.1, card_y + 0.43, w_status - 0.2, 0.2, "Frequency Range:", font_size=9, bold=True)
        add_text(status_x + 0.1, card_y + 0.61, w_status - 0.2, 0.2, f"Kurtosis Threshold: {k_thresh}, Kurtosis Detection: {k_val}", font_size=9, bold=True)
        add_text(status_x + 0.1, card_y + 0.79, w_status - 0.2, 0.2, f"Peak Factor Threshold: {p_thresh}, Peak Factor: {p_val}", font_size=9, bold=True)
    else:
        det_status = csv_res.get('detection_status', 'N/A')
        add_text(status_x + 0.1, card_y + 0.3, w_status - 0.2, 0.3, f"Detection Status: {det_status}", font_size=11, bold=True)
        add_text(status_x + 0.1, card_y + 0.6, w_status - 0.2, 0.3, f"Notification Level: {csv_level}", font_size=11, bold=True)

    # 4. Image Frames
    frame_y = 2.5
    
    # Custom widths for Leakage/Vibration (3 images)
    if raw_type in ['leakage_inspection', 'vibration_inspection']:
        f1_w = 4.8
        f2_w = 7.5
    else:
        f1_w = 6.0
        f2_w = 6.0
    
    frame_h = 3.5
    
    # Left Frame (Robot/Map Position Image from extracted PDF)
    f1_rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(frame_y), Inches(f1_w), Inches(frame_h))
    f1_rect.fill.solid()
    f1_rect.fill.fore_color.rgb = CARD_BG
    f1_rect.line.visible = False
    
    takescreen_dir = '/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/TakeScreen'
    robot_img_path = os.path.join(takescreen_dir, f'{name}.jpg')
    
    if os.path.exists(robot_img_path):
        try:
            slide.shapes.add_picture(robot_img_path, Inches(0.5), Inches(frame_y), width=Inches(f1_w), height=Inches(frame_h))
        except Exception as e:
            print(f"Error adding robot image {robot_img_path}: {e}")
            add_text(0.5, frame_y + (frame_h/2) - 0.2, f1_w, 0.4, "Robot Image Corrupt", font_size=10, color=TEXT_SECONDARY, alignment=PP_ALIGN.CENTER)
    else:
        add_text(0.5, frame_y + (frame_h/2) - 0.2, f1_w, 0.4, "Robot & Map Image Not Found", font_size=10, color=TEXT_SECONDARY, alignment=PP_ALIGN.CENTER)

    # Right Frame (Inspection Results)
    f2_x = SLIDE_WIDTH - 0.5 - f2_w
    f2_rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(f2_x), Inches(frame_y), Inches(f2_w), Inches(frame_h))
    f2_rect.fill.solid()
    f2_rect.fill.fore_color.rgb = CARD_BG
    f2_rect.line.visible = False
    
    images = find_images(name, raw_type)
    if not images:
        add_text(f2_x, frame_y + (frame_h/2) - 0.2, f2_w, 0.4, "Inspection Result Image Not Found", font_size=12, color=TEXT_SECONDARY, alignment=PP_ALIGN.CENTER)
    else:
        num_imgs = len(images)
        img_w = f2_w / num_imgs if num_imgs > 0 else f2_w
        for i, img_path in enumerate(images):
            left_offset = f2_x + (i * img_w)
            try:
                slide.shapes.add_picture(img_path, Inches(left_offset), Inches(frame_y), width=Inches(img_w), height=Inches(frame_h))
            except Exception as e:
                print(f"Error adding image {img_path}: {e}")

    # 5. Description Area (Now with Dynamic Discussion)
    desc_y = 6.2
    add_text(0.5, desc_y, 2.0, 0.3, "Description / Discussion", font_size=10, color=TEXT_SECONDARY)
    
    discussion_text = get_discussion(name, raw_type, csv_res, csv_level)
    add_text(0.5, desc_y + 0.25, 12.0, 0.8, discussion_text, font_size=11, color=TEXT_PRIMARY)

    # 6. Pagination Dots
    dot_y = 7.1
    dot_size = 0.06
    for i in range(3):
        dot_color = ACCENT_BLUE if i == 0 else RGBColor(50, 60, 80)
        dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.5 + (i * 0.15)), Inches(dot_y), Inches(dot_size), Inches(dot_size))
        dot.fill.solid()
        dot.fill.fore_color.rgb = dot_color
        dot.line.visible = False

# Load Notification Data from CSV
notifications = {}
csv_path = '/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/mission-332/notification_332_2026-03-18_2026-04-24.csv'
if os.path.exists(csv_path):
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['action_name']
            # Parse result string to dict safely
            try:
                res_str = row['result'].replace("'", '"').replace("True", "true").replace("False", "false")
                row['result_dict'] = json.loads(res_str)
            except:
                try:
                    row['result_dict'] = ast.literal_eval(row['result'])
                except:
                    row['result_dict'] = {}
            notifications[name] = row

def get_discussion(name, raw_type, csv_res, csv_level):
    level = csv_level.lower()
    
    if raw_type == 'thermal_inspection':
        max_t = csv_res.get('max_temperature', 0)
        # We don't have the threshold in this function but we can use generic
        if level == 'pass':
            return "The thermal camera was utilized to monitor the surface temperature of the equipment. The test results indicate that the operating temperature is within the normal range."
        else:
            return f"The thermal camera detected an elevated temperature of {max_t}°C, which may indicate overheating or abnormal operating conditions."
            
    elif raw_type == 'leakage_inspection':
        is_leak = csv_res.get('is_leak', False)
        if is_leak:
            return "The Acoustic Imager successfully detected and localized an air leak, pinpointing its exact coordinates as shown in the visual overlay."
        else:
            return "The Acoustic Imager monitored the area for ultrasonic leak patterns. No significant air or gas leaks were detected, indicating the system is airtight."
            
    elif 'gauge' in raw_type:
        status = csv_res.get('detection_status', True)
        if not status:
            return "Due to the absence of clear indicator markings or color-coded safe ranges on the gauge, the system could not verify the status, resulting in a critical detection output."
        else:
            return "The vision system successfully identified the gauge reading. The indicator is positioned within the standard operating range."
            
    elif 'vibration' in raw_type:
        if level == 'pass':
            return "The system analyzed acoustic vibration patterns to assess the equipment's operational condition. The results indicate that it is functioning normally with no signs of mechanical damage."
        else:
            return "Acoustic vibration analysis detected irregular frequency patterns or high peak factors, suggesting potential mechanical wear or bearing issues."
            
    elif 'asset' in raw_type or 'loto' in raw_type:
        status = csv_res.get('detection_status', True)
        if not status:
            return "The vision system identified an anomaly in the designated area, detecting that certain equipment or protective assets were missing or not in their correct state."
        else:
            return "The vision system confirmed that all assets and safety indicators (LOTO) are in their correct positions and states."
            
    return f"The automated inspection for {name} was completed. The system evaluated the {raw_type} data and the results were recorded as {level}."

def add_summary_slide(prs, inspection_points, notifications):
    blank_slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank_slide_layout)
    
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = BG_COLOR
    
    def add_text(left, top, width, height, text, font_size=12, bold=False, color=TEXT_PRIMARY, alignment=PP_ALIGN.LEFT):
        txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = txBox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = text
        p.alignment = alignment
        p.font.size = Pt(font_size)
        p.font.bold = bold
        p.font.color.rgb = color
        p.font.name = 'Arial'
        return txBox

    # Title
    add_text(0.5, 0.4, 12, 0.8, "Inspection Summary Report", font_size=40, bold=True, alignment=PP_ALIGN.CENTER)
    
    # Logo
    logo_path = '/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/gensurv-logo.jpg'
    if os.path.exists(logo_path):
        slide.shapes.add_picture(logo_path, Inches(12.733), Inches(0.0), height=Inches(0.6))

    # Aggregate Data
    summary_data = {} # {type: {level: count}}
    total_counts = {"pass": 0, "fail": 0, "missing": 0}
    missing_points = []
    
    for point in inspection_points:
        name = point.get('Node_info', '')
        raw_insp = point.get('Inspection', 'General')
        
        # Split LOTO from Asset if name contains 'loto'
        if raw_insp == 'asset_inspection' and 'loto' in name.lower():
            raw_type = 'Loto Inspection'
        else:
            raw_type = raw_insp.replace('_', ' ').title()
        
        notif = notifications.get(name)
        images = find_images(name, raw_insp)
        
        if not notif or not images:
            level = 'missing'
            if not notif and not images:
                missing_points.append(f"{name} (No CSV, No Images)")
            elif not notif:
                missing_points.append(f"{name} (No CSV)")
            elif not images:
                missing_points.append(f"{name} (No Images)")
        else:
            level = notif.get('notification_level', 'N/A').lower()
        
        if raw_type not in summary_data:
            summary_data[raw_type] = Counter()
        
        summary_data[raw_type][level] += 1
        
        if level == 'pass':
            total_counts['pass'] += 1
        elif level == 'missing':
            total_counts['missing'] += 1
        else:
            total_counts['fail'] += 1

    if missing_points:
        print(f"\n[Warning] Missing data detected for {len(missing_points)} points:")
        for mp in missing_points:
            print(f"  - {mp}")
        print()

    # Main Stats Cards
    card_y = 1.5
    card_w = 2.8
    card_h = 1.2
    spacing = 0.4
    
    start_x = (SLIDE_WIDTH - (4 * card_w + 3 * spacing)) / 2
    
    # Total Points Card
    t_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(start_x), Inches(card_y), Inches(card_w), Inches(card_h))
    t_card.fill.solid()
    t_card.fill.fore_color.rgb = CARD_BG
    t_card.line.visible = False
    add_text(start_x + 0.1, card_y + 0.1, card_w - 0.2, 0.3, "TOTAL POINTS", font_size=12, color=TEXT_SECONDARY, alignment=PP_ALIGN.CENTER)
    add_text(start_x + 0.1, card_y + 0.4, card_w - 0.2, 0.6, str(len(inspection_points)), font_size=36, bold=True, color=RGBColor(255, 255, 255), alignment=PP_ALIGN.CENTER)

    # Pass Card
    p_x = start_x + card_w + spacing
    p_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(p_x), Inches(card_y), Inches(card_w), Inches(card_h))
    p_card.fill.solid()
    p_card.fill.fore_color.rgb = CARD_BG
    p_card.line.visible = False
    add_text(p_x + 0.1, card_y + 0.1, card_w - 0.2, 0.3, "TOTAL PASS", font_size=12, color=TEXT_SECONDARY, alignment=PP_ALIGN.CENTER)
    add_text(p_x + 0.1, card_y + 0.4, card_w - 0.2, 0.6, str(total_counts['pass']), font_size=36, bold=True, color=RGBColor(74, 222, 128), alignment=PP_ALIGN.CENTER)

    # Fail/Notification Card
    f_x = p_x + card_w + spacing
    f_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(f_x), Inches(card_y), Inches(card_w), Inches(card_h))
    f_card.fill.solid()
    f_card.fill.fore_color.rgb = CARD_BG
    f_card.line.visible = False
    add_text(f_x + 0.1, card_y + 0.1, card_w - 0.2, 0.3, "NOTIFICATIONS", font_size=12, color=TEXT_SECONDARY, alignment=PP_ALIGN.CENTER)
    add_text(f_x + 0.1, card_y + 0.4, card_w - 0.2, 0.6, str(total_counts['fail']), font_size=36, bold=True, color=RGBColor(248, 113, 113), alignment=PP_ALIGN.CENTER)

    # Missing Card
    m_x = f_x + card_w + spacing
    m_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(m_x), Inches(card_y), Inches(card_w), Inches(card_h))
    m_card.fill.solid()
    m_card.fill.fore_color.rgb = CARD_BG
    m_card.line.visible = False
    add_text(m_x + 0.1, card_y + 0.1, card_w - 0.2, 0.3, "MISSING DATA", font_size=12, color=TEXT_SECONDARY, alignment=PP_ALIGN.CENTER)
    add_text(m_x + 0.1, card_y + 0.4, card_w - 0.2, 0.6, str(total_counts['missing']), font_size=36, bold=True, color=RGBColor(250, 204, 21), alignment=PP_ALIGN.CENTER)

    # Breakdown Table Header
    table_y = 3.2
    add_text(0.5, table_y, 4, 0.4, "Breakdown by Inspection Type", font_size=18, bold=True)
    
    # Table Column Headers
    header_y = table_y + 0.5
    col_w_type = 3.5
    col_w_pass = 2.0
    col_w_fail = 2.0
    col_w_miss = 2.0
    
    def draw_row(y, t1, t2, t3, t4, is_header=False):
        row_h = 0.5
        bg = RGBColor(40, 50, 70) if is_header else CARD_BG
        
        start_x = (SLIDE_WIDTH - (col_w_type + col_w_pass + col_w_fail + col_w_miss)) / 2
        
        # Type
        r1 = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(start_x), Inches(y), Inches(col_w_type), Inches(row_h))
        r1.fill.solid()
        r1.fill.fore_color.rgb = bg
        r1.line.color.rgb = RGBColor(60, 70, 90)
        add_text(start_x + 0.1, y + 0.05, col_w_type - 0.2, row_h, t1, font_size=14, bold=is_header)
        
        # Pass
        x2 = start_x + col_w_type
        r2 = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x2), Inches(y), Inches(col_w_pass), Inches(row_h))
        r2.fill.solid()
        r2.fill.fore_color.rgb = bg
        r2.line.color.rgb = RGBColor(60, 70, 90)
        add_text(x2, y + 0.05, col_w_pass, row_h, t2, font_size=14, bold=is_header, alignment=PP_ALIGN.CENTER)
        
        # Fail
        x3 = x2 + col_w_pass
        r3 = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x3), Inches(y), Inches(col_w_fail), Inches(row_h))
        r3.fill.solid()
        r3.fill.fore_color.rgb = bg
        r3.line.color.rgb = RGBColor(60, 70, 90)
        add_text(x3, y + 0.05, col_w_fail, row_h, t3, font_size=14, bold=is_header, alignment=PP_ALIGN.CENTER)
        
        # Missing
        x4 = x3 + col_w_fail
        r4 = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x4), Inches(y), Inches(col_w_miss), Inches(row_h))
        r4.fill.solid()
        r4.fill.fore_color.rgb = bg
        r4.line.color.rgb = RGBColor(60, 70, 90)
        add_text(x4, y + 0.05, col_w_miss, row_h, t4, font_size=14, bold=is_header, alignment=PP_ALIGN.CENTER)

    draw_row(header_y, "Inspection Type", "Pass Count", "Notification", "Missing", is_header=True)
    
    current_y = header_y + 0.5
    for raw_type, counts in sorted(summary_data.items()):
        pass_count = counts.get('pass', 0)
        miss_count = counts.get('missing', 0)
        # Sum everything else as fail/false
        fail_count = sum(c for lvl, c in counts.items() if lvl not in ('pass', 'missing'))
        draw_row(current_y, raw_type, str(pass_count), str(fail_count), str(miss_count))
        current_y += 0.5



def main():
    json_path = '/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/path/new-dry-full.json'
    output_path = '/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/inspection_slides.pptx'
    
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, 'r') as f:
        data = json.load(f)
        
    inspection_points = [p for p in data if p.get('PointInfo') == 1]
    
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_WIDTH)
    prs.slide_height = Inches(SLIDE_HEIGHT)

    print(f"Found {len(inspection_points)} inspection points. Generating slides...")
    for i, point in enumerate(inspection_points):
        add_slide(prs, point, i, len(inspection_points))
        if (i + 1) % 10 == 0:
            print(f"Generated {i + 1} slides...")
    
    # Add final summary slide
    add_summary_slide(prs, inspection_points, notifications)
    
    prs.save(output_path)

    print(f"Successfully generated {output_path}")

if __name__ == "__main__":
    main()
