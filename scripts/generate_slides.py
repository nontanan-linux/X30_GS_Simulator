import json
import os

def generate_html(data):
    # Filter points with PointInfo == 1
    inspection_points = [p for p in data if p.get('PointInfo') == 1]
    
    html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Inspection Point Slides</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Outfit:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #6366f1;
            --bg-dark: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.7);
            --border-color: rgba(255, 255, 255, 0.1);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent: #10b981;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-primary);
            overflow-x: hidden;
        }

        .presentation-container {
            width: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 40px 0;
        }

        .slide {
            width: 90vw;
            max-width: 1200px;
            aspect-ratio: 16 / 9;
            background: radial-gradient(circle at top left, #1e293b, #0f172a);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            margin-bottom: 80px;
            padding: 40px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: auto 1fr;
            gap: 24px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            position: relative;
            overflow: hidden;
            break-after: page;
        }

        .slide::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle at 10% 10%, rgba(99, 102, 241, 0.05), transparent);
            pointer-events: none;
        }

        .header {
            grid-column: 1 / -1;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 16px;
        }

        .header h1 {
            font-family: 'Outfit', sans-serif;
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(to right, #fff, #94a3b8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .info-panel {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .info-item {
            display: flex;
            flex-direction: column;
        }

        .info-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-secondary);
            margin-bottom: 4px;
        }

        .info-value {
            font-size: 1.1rem;
            font-weight: 600;
            color: #fff;
        }

        .visual-panel {
            display: grid;
            grid-template-rows: 1fr 1fr;
            gap: 20px;
        }

        .image-frame {
            background: var(--card-bg);
            border: 2px dashed rgba(255, 255, 255, 0.15);
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }

        .image-frame:hover {
            border-color: var(--primary);
            background: rgba(99, 102, 241, 0.05);
        }

        .image-placeholder-text {
            color: var(--text-secondary);
            font-size: 0.85rem;
            text-align: center;
            padding: 10px;
        }

        .dual-image {
            display: grid;
            grid-template-columns: 1fr 1fr;
            height: 100%;
            width: 100%;
        }

        .divider {
            width: 1px;
            background: rgba(255, 255, 255, 0.1);
            height: 60%;
            align-self: center;
        }

        .description-box {
            grid-column: 1 / 2;
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .description-header {
            font-size: 0.75rem;
            text-transform: uppercase;
            color: var(--text-secondary);
        }

        .description-content {
            font-size: 0.95rem;
            line-height: 1.6;
            color: #cbd5e1;
            min-height: 80px;
        }

        .footer {
            position: absolute;
            bottom: 20px;
            right: 40px;
            font-size: 0.7rem;
            color: var(--text-secondary);
            opacity: 0.5;
        }

        @media print {
            .slide {
                margin: 0;
                width: 100vw;
                height: 100vh;
                border: none;
                box-shadow: none;
                break-after: always;
            }
        }
    </style>
</head>
<body>
    <div class="presentation-container">
    """

    for p in inspection_points:
        name = p.get('Node_info', 'N/A')
        type_ = p.get('Inspection', 'General').replace('_', ' ').title()
        zone = p.get('Zone', 'N/A')
        floor = p.get('MapName', 'N/A').replace('_', ' ').title()
        
        html_template += f"""
        <!-- Slide: {name} -->
        <div class="slide" id="slide-{name}">
            <div class="header">
                <h1>{name}</h1>
                <div class="info-item" style="text-align: right;">
                    <span class="info-label">Floor</span>
                    <span class="info-value">{floor}</span>
                </div>
            </div>

            <div class="info-panel">
                <div class="info-item">
                    <span class="info-label">Inspection Point Name</span>
                    <span class="info-value">{name}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Inspection Type</span>
                    <span class="info-value" style="color: var(--accent);">{type_}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Zone</span>
                    <span class="info-value">{zone}</span>
                </div>
                
                <div class="description-box">
                    <span class="description-header">Description</span>
                    <div class="description-content">
                        <!-- Placeholder for description -->
                    </div>
                </div>
            </div>

            <div class="visual-panel">
                <div class="image-frame">
                    <div class="dual-image">
                        <div class="image-placeholder-text">Robot & Inspection Point Image</div>
                        <div class="divider"></div>
                        <div class="image-placeholder-text">Map Point Image</div>
                    </div>
                </div>
                <div class="image-frame">
                    <div class="image-placeholder-text">Inspection Result Image</div>
                </div>
            </div>

            <div class="footer">NESTLE CAT GS | {name}</div>
        </div>
        """

    html_template += """
    </div>
</body>
</html>
    """
    return html_template

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    json_path = os.path.join(project_root, 'resource', 'path', 'new-dry-full.json')
    output_path = os.path.join(project_root, 'inspection_slides.html')
    
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, 'r') as f:
        data = json.load(f)
        
    html_content = generate_html(data)
    
    with open(output_path, 'w') as f:
        f.write(html_content)
        
    print(f"Successfully generated {output_path}")

if __name__ == "__main__":
    main()
