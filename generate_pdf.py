import os
import re
import subprocess

# Paths
MD_PATH = "/home/k3and4/.gemini/antigravity/brain/76e414de-c1c8-4fe5-bb55-3b8af2b81268/system_requirements_specification.md"
HTML_PATH = "/media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility/temp_requirements.html"
PDF_PATH = "/media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility/Care_Link_System_Requirements.pdf"

def simple_md_to_html(md_text):
    """Simple Markdown to HTML converter tailored for our SRS document."""
    html = md_text

    # Escape HTML special characters except formatting
    html = html.replace("&", "&amp;")

    # Headers
    html = re.sub(r"^# (.*?)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.*?)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.*?)$", r"3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^#### (.*?)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)

    # Code blocks (ASCII art & Diagrams)
    def code_block_sub(match):
        code_content = match.group(1).replace("&amp;", "&").replace("<", "&lt;").replace(">", "&gt;")
        return f'<pre class="diagram"><code>{code_content}</code></pre>'
    html = re.sub(r"```text\s*\n(.*?)\n```", code_block_sub, html, flags=re.DOTALL)
    html = re.sub(r"```\s*\n(.*?)\n```", code_block_sub, html, flags=re.DOTALL)

    # Bold and inline code
    html = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"`(.*?)`", r"<code>\1</code>", html)

    # Tables
    def table_sub(match):
        table_text = match.group(0).strip()
        lines = [line.strip() for line in table_text.split("\n") if line.strip()]
        if len(lines) < 2:
            return table_text
        
        headers = [c.strip() for c in lines[0].strip("|").split("|")]
        # Skip separator line (line 1)
        rows = []
        for line in lines[2:]:
            cols = [c.strip() for c in line.strip("|").split("|")]
            rows.append(cols)

        t_html = '<table class="styled-table"><thead><tr>'
        for h in headers:
            t_html += f'<th>{h}</th>'
        t_html += '</tr></thead><tbody>'
        for r in rows:
            t_html += '<tr>'
            for c in r:
                t_html += f'<td>{c}</td>'
            t_html += '</tr>'
        t_html += 'tbody></table>'
        return t_html

    table_pattern = r"(?:^\|.*\|\s*\n)+"
    html = re.sub(table_pattern, table_sub, html, flags=re.MULTILINE)

    # Horizontal rules
    html = re.sub(r"^---$", r"<hr>", html, flags=re.MULTILINE)

    # Lists
    def list_sub(match):
        items = match.group(0).strip().split("\n")
        l_html = "<ul>"
        for item in items:
            content = re.sub(r"^\s*[\*\-]\s*", "", item)
            l_html += f"<li>{content}</li>"
        l_html += "</ul>"
        return l_html
    html = re.sub(r"(?:^\s*[\*\-]\s+.*$\n?)+", list_sub, html, flags=re.MULTILINE)

    # Paragraphs (lines that aren't tags)
    lines = html.split("\n")
    processed_lines = []
    for line in lines:
        l = line.strip()
        if l and not l.startswith("<") and not l.endswith(">"):
            processed_lines.append(f"<p>{l}</p>")
        else:
            processed_lines.append(line)
    
    return "\n".join(processed_lines)

# Read Markdown
with open(MD_PATH, "r", encoding="utf-8") as f:
    md_content = f.read()

body_html = simple_md_to_html(md_content)

# Styled Full HTML Template
full_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>介護施設統合AIシステム「ケア・リンク」要件仕様書</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');

        @page {{
            size: A4;
            margin: 18mm 15mm 18mm 15mm;
        }}

        body {{
            font-family: 'Noto Sans JP', 'Hiragino Kaku Gothic ProN', 'Meiryo', sans-serif;
            color: #1e293b;
            line-height: 1.6;
            font-size: 11pt;
            background: white;
        }}

        h1 {{
            font-size: 20pt;
            color: #0f172a;
            border-bottom: 3px solid #2563eb;
            padding-bottom: 8px;
            margin-top: 24px;
            margin-bottom: 16px;
            page-break-before: always;
        }}

        h1:first-of-type {{
            page-break-before: avoid;
        }}

        h2 {{
            font-size: 15pt;
            color: #1e3a8a;
            border-left: 5px solid #2563eb;
            padding-left: 10px;
            margin-top: 20px;
            margin-bottom: 12px;
            page-break-after: avoid;
        }}

        h3 {{
            font-size: 12pt;
            color: #0f172a;
            margin-top: 14px;
            margin-bottom: 8px;
            page-break-after: avoid;
        }}

        p {{
            margin-bottom: 10px;
            text-align: justify;
        }}

        hr {{
            border: none;
            border-top: 1px solid #cbd5e1;
            margin: 20px 0;
        }}

        ul {{
            margin-bottom: 12px;
            padding-left: 20px;
        }}

        li {{
            margin-bottom: 4px;
        }}

        strong {{
            color: #0f172a;
        }}

        code {{
            background-color: #f1f5f9;
            color: #0f172a;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 9.5pt;
        }}

        pre.diagram {{
            background-color: #0f172a;
            color: #38bdf8;
            padding: 14px;
            border-radius: 8px;
            font-family: 'Courier New', Consolas, monospace;
            font-size: 8.5pt;
            line-height: 1.35;
            overflow-x: auto;
            margin: 14px 0;
            page-break-inside: avoid;
        }}

        pre.diagram code {{
            background: none;
            color: inherit;
            padding: 0;
        }}

        .styled-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
            font-size: 10pt;
            page-break-inside: avoid;
        }}

        .styled-table th, .styled-table td {{
            border: 1px solid #cbd5e1;
            padding: 8px 12px;
            text-align: left;
        }}

        .styled-table th {{
            background-color: #f1f5f9;
            color: #0f172a;
            font-weight: 700;
        }}

        .styled-table tr:nth-child(even) {{
            background-color: #f8fafc;
        }}

        .doc-header {{
            text-align: center;
            padding-bottom: 20px;
            border-bottom: 2px solid #0f172a;
            margin-bottom: 30px;
        }}

        .doc-header h0 {{
            font-size: 22pt;
            font-weight: 900;
            color: #0f172a;
            display: block;
        }}

        .doc-header .sub {{
            font-size: 11pt;
            color: #64748b;
            margin-top: 6px;
        }}
    </style>
</head>
<body>
    <div class="doc-header">
        <h0>介護施設統合AIシステム「ケア・リンク」</h0>
        <div class="sub">要求定義書 兼 要件仕様書 (System Requirements Specification)</div>
    </div>
    {body_html}
</body>
</html>
"""

# Save Temp HTML
with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(full_html)

print("Generated HTML, compiling PDF via headless Chrome...")

# Run Headless Chrome to generate PDF
chrome_cmd = [
    "google-chrome",
    "--headless",
    "--disable-gpu",
    "--no-pdf-header-footer",
    f"--print-to-pdf={PDF_PATH}",
    HTML_PATH
]

res = subprocess.run(chrome_cmd, capture_output=True, text=True)
if res.returncode == 0:
    print(f"PDF successfully generated at: {PDF_PATH}")
    if os.path.exists(HTML_PATH):
        os.remove(HTML_PATH)
else:
    print(f"Error generating PDF: {res.stderr}")
