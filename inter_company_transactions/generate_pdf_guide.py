#!/usr/bin/env python3
"""
Generate a professional PDF version of the Inter-Company Transactions User Guide.
This script builds a multi-page PDF using standard Python without external dependencies.
"""

import io
import os
import sys
import textwrap
from pathlib import Path


def create_pdf(output_path=None):
    # Read the markdown content
    script_dir = os.path.dirname(os.path.abspath(__file__))
    md_path = os.path.join(script_dir, "USER_GUIDE.md")

    if not os.path.exists(md_path):
        md_path = os.path.join(script_dir, "..", "USER_GUIDE.md")

    lines = Path(md_path).read_text(encoding="utf-8").splitlines(True)

    # Determine default output path
    if not output_path:
        public_dir = os.path.join(script_dir, "public")
        os.makedirs(public_dir, exist_ok=True)
        output_path = os.path.join(public_dir, "Inter_Company_Transactions_User_Guide.pdf")

    # Dynamic line layout with text wrapping and height calculation
    pages = []
    current_page_items = []
    current_y = 705

    def push_page():
        nonlocal current_page_items, current_y
        if current_page_items:
            pages.append(current_page_items)
            current_page_items = []
        current_y = 735

    in_code_block = False
    for raw_line in lines:
        line = raw_line.rstrip()

        # Determine formatting type and height
        if line.startswith("# "):
            text = line[2:].strip()
            # Clean special characters
            text_clean = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            needed_h = 24
            if current_y - needed_h < 55:
                push_page()
            current_page_items.append(('h1', text_clean, current_y))
            current_y -= needed_h

        elif line.startswith("## "):
            text = line[3:].strip()
            text_clean = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            needed_h = 20
            if current_y - needed_h < 55:
                push_page()
            current_page_items.append(('h2', text_clean, current_y))
            current_y -= needed_h

        elif line.startswith("### "):
            text = line[4:].strip()
            text_clean = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            needed_h = 17
            if current_y - needed_h < 55:
                push_page()
            current_page_items.append(('h3', text_clean, current_y))
            current_y -= needed_h

        elif line.startswith("#### "):
            text = line[5:].strip()
            text_clean = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            needed_h = 15
            if current_y - needed_h < 55:
                push_page()
            current_page_items.append(('h4', text_clean, current_y))
            current_y -= needed_h

        elif line.strip() == "---":
            needed_h = 12
            if current_y - needed_h < 55:
                push_page()
            current_page_items.append(('hr', '', current_y))
            current_y -= needed_h

        elif line.startswith("```"):
            in_code_block = not in_code_block
            current_y -= 4
            if current_y < 55:
                push_page()

        elif in_code_block:
            text_clean = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            needed_h = 9.5
            if current_y - needed_h < 55:
                push_page()
            current_page_items.append(('code', text_clean[:100], current_y))
            current_y -= needed_h

        elif line.startswith("* ") or line.startswith("- "):
            text = line[2:].strip()
            wrapped = textwrap.wrap(text, width=80)
            for idx, w in enumerate(wrapped):
                w_clean = w.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
                prefix = "\\225 " if idx == 0 else "  "
                needed_h = 12
                if current_y - needed_h < 55:
                    push_page()
                current_page_items.append(('bullet', f"{prefix}{w_clean}", current_y))
                current_y -= needed_h

        elif line.startswith("   - ") or line.startswith("  * ") or line.startswith("    - "):
            text = line.lstrip(" -*").strip()
            wrapped = textwrap.wrap(text, width=76)
            for idx, w in enumerate(wrapped):
                w_clean = w.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
                prefix = "- " if idx == 0 else "  "
                needed_h = 11.5
                if current_y - needed_h < 55:
                    push_page()
                current_page_items.append(('subbullet', f"{prefix}{w_clean}", current_y))
                current_y -= needed_h

        elif not line.strip():
            current_y -= 6
            if current_y < 55:
                push_page()

        else:
            wrapped = textwrap.wrap(line, width=86)
            for w in wrapped:
                w_clean = w.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
                needed_h = 11.5
                if current_y - needed_h < 55:
                    push_page()
                current_page_items.append(('body', w_clean, current_y))
                current_y -= needed_h

    if current_page_items:
        pages.append(current_page_items)

    total_pages = len(pages)

    # Lay out PDF objects:
    # 1: Catalog
    # 2: Pages
    # 3: Regular Font (Helvetica)
    # 4: Bold Font (Helvetica-Bold)
    # 5: Monospace Font (Courier)
    # 6, 7 (Page, Content stream)...
    next_id = 6
    page_entries = []

    for idx, p_items in enumerate(pages):
        page_id = next_id
        content_id = next_id + 1
        next_id += 2
        page_entries.append((page_id, content_id, p_items, idx + 1))

    obj_catalog = "<< /Type /Catalog /Pages 2 0 R >>"
    kids_str = " ".join([f"{p[0]} 0 R" for p in page_entries])
    obj_pages = f"<< /Type /Pages /Kids [{kids_str}] /Count {total_pages} >>"
    obj_font = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    obj_font_bold = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"
    obj_font_mono = "<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"

    pdf_objs = [
        (1, obj_catalog),
        (2, obj_pages),
        (3, obj_font),
        (4, obj_font_bold),
        (5, obj_font_mono)
    ]

    for page_id, content_id, p_items, page_num in page_entries:
        page_dict = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R /Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> >>"
        pdf_objs.append((page_id, page_dict))

        stream_cmds = []
        stream_cmds.append("q")

        # Header banner or running header
        if page_num == 1:
            # Header bar
            stream_cmds.append("0.12 0.23 0.53 rg") # Corporate deep blue
            stream_cmds.append("40 730 532 32 re f")
            stream_cmds.append("1 1 1 rg") # White text
            stream_cmds.append("BT /F2 13 Tf 50 742 Td (INTER-COMPANY TRANSACTIONS FOR ERPNEXT) Tj ET")
            stream_cmds.append("0 0 0 rg") # Reset black
        else:
            # Subtle running header
            stream_cmds.append("0.4 0.4 0.4 rg")
            stream_cmds.append("BT /F1 9 Tf 40 760 Td (Inter-Company Transactions - Enterprise User Guide & Multi-Entity Tutorial) Tj ET")
            stream_cmds.append("0.8 0.8 0.8 RG 40 752 m 572 752 l S")
            stream_cmds.append("0 0 0 rg")

        # Running footer
        stream_cmds.append("0.4 0.4 0.4 rg")
        stream_cmds.append("0.8 0.8 0.8 RG 40 40 m 572 40 l S")
        stream_cmds.append(f"BT /F1 9 Tf 520 28 Td (Page {page_num} of {total_pages}) Tj ET")
        stream_cmds.append("0 0 0 rg")

        for item_type, text, y in p_items:
            if item_type == 'h1':
                stream_cmds.append(f"0.12 0.23 0.53 rg BT /F2 13 Tf 40 {y} Td ({text}) Tj ET 0 0 0 rg")
            elif item_type == 'h2':
                stream_cmds.append(f"0.15 0.3 0.6 rg BT /F2 11 Tf 40 {y} Td ({text}) Tj ET 0 0 0 rg")
            elif item_type == 'h3':
                stream_cmds.append(f"0.2 0.2 0.2 rg BT /F2 10 Tf 40 {y} Td ({text}) Tj ET 0 0 0 rg")
            elif item_type == 'h4':
                stream_cmds.append(f"0.25 0.25 0.25 rg BT /F2 9.5 Tf 40 {y} Td ({text}) Tj ET 0 0 0 rg")
            elif item_type == 'hr':
                stream_cmds.append(f"0.85 0.85 0.85 RG 40 {y} m 572 {y} l S 0 0 0 rg")
            elif item_type == 'bullet':
                stream_cmds.append(f"BT /F1 8.5 Tf 50 {y} Td ({text}) Tj ET")
            elif item_type == 'subbullet':
                stream_cmds.append(f"BT /F1 8.5 Tf 65 {y} Td ({text}) Tj ET")
            elif item_type == 'code':
                stream_cmds.append(f"0.96 0.97 0.98 rg 40 {y-1.5} 532 9.5 re f")
                stream_cmds.append(f"0.15 0.2 0.35 rg BT /F3 7 Tf 44 {y} Td ({text}) Tj ET 0 0 0 rg")
            else:
                stream_cmds.append(f"BT /F1 8.5 Tf 40 {y} Td ({text}) Tj ET")

        stream_cmds.append("Q")
        stream_data = "\n".join(stream_cmds).encode('latin-1', 'replace')
        content_dict = f"<< /Length {len(stream_data)} >>\nstream\n{stream_data.decode('latin-1')}\nendstream"
        pdf_objs.append((content_id, content_dict))

    # Sort objects by id
    pdf_objs.sort(key=lambda x: x[0])

    # Write PDF file with accurate xref table
    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    buf.write(b"%PDF-1.4\n")
    offsets = {}
    for obj_id, obj_body in pdf_objs:
        offsets[obj_id] = buf.tell()
        buf.write(f"{obj_id} 0 obj\n{obj_body}\nendobj\n".encode('latin-1'))

    xref_offset = buf.tell()
    total_objs = len(pdf_objs) + 1
    buf.write(f"xref\n0 {total_objs}\n".encode('latin-1'))
    buf.write(b"0000000000 65535 f \n")
    for obj_id in range(1, total_objs):
        pos = offsets.get(obj_id, 0)
        buf.write(f"{pos:010d} 00000 n \n".encode('latin-1'))

    buf.write(f"trailer\n<< /Size {total_objs} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode('latin-1'))
    out_file.write_bytes(buf.getvalue())

    print(f"Successfully generated User Guide PDF at {output_path} ({os.path.getsize(output_path)} bytes, {total_pages} pages)")
    return output_path

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_public = os.path.join(script_dir, "public", "Inter_Company_Transactions_User_Guide.pdf")
    out = sys.argv[1] if len(sys.argv) > 1 else target_public
    pdf_path = create_pdf(out)

    # Also copy to root for quick access
    root_pdf = os.path.join(script_dir, "..", "Inter_Company_Transactions_User_Guide.pdf")
    try:
        import shutil
        shutil.copyfile(pdf_path, root_pdf)
        print(f"Copied to root: {root_pdf}")
    except Exception as e:
        print(f"Notice: {e}")

