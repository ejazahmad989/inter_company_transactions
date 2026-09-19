#!/usr/bin/env python3
"""
Generate a professional PDF version of the Inter-Company Transactions User Guide.
This script builds a multi-page PDF using standard Python without external dependencies.
"""

import sys
import os

def create_pdf(output_path="inter_company_user_guide.pdf"):
    # Read the markdown content
    script_dir = os.path.dirname(os.path.abspath(__file__))
    md_path = os.path.join(script_dir, "USER_GUIDE.md")
    
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Simple, elegant PDF page builder
    pages = []
    current_page_lines = []
    
    # Clean text lines for printing
    for raw_line in lines:
        line = raw_line.rstrip()
        # Escape parenthesis and backslashes for PDF text encoding
        line_clean = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        current_page_lines.append(line_clean)
        if len(current_page_lines) >= 54:
            pages.append(current_page_lines)
            current_page_lines = []
    if current_page_lines:
        pages.append(current_page_lines)

    total_pages = len(pages)
    
    # PDF binary stream construction
    objects = []
    
    def add_object(content):
        objects.append(content)
        return len(objects)

    # Obj 1: Catalog (placeholder, updated at end)
    # Obj 2: Pages (placeholder)
    
    page_obj_ids = []
    font_obj_id = 3 # Will define font as obj 3
    bold_font_obj_id = 4 # Will define bold font as obj 4

    # We will lay out objects:
    # 1: Catalog
    # 2: Pages
    # 3: Regular Font (Helvetica)
    # 4: Bold Font (Helvetica-Bold)
    # Then each page:
    # 5, 6 (Page, Content stream), 7, 8...
    
    next_id = 5
    page_entries = []

    for idx, p_lines in enumerate(pages):
        page_id = next_id
        content_id = next_id + 1
        next_id += 2
        page_entries.append((page_id, content_id, p_lines, idx + 1))

    # Prepare PDF objects
    obj_catalog = "<< /Type /Catalog /Pages 2 0 R >>"
    
    kids_str = " ".join([f"{p[0]} 0 R" for p in page_entries])
    obj_pages = f"<< /Type /Pages /Kids [{kids_str}] /Count {total_pages} >>"
    obj_font = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    obj_font_bold = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"
    
    pdf_objs = [
        (1, obj_catalog),
        (2, obj_pages),
        (3, obj_font),
        (4, obj_font_bold)
    ]

    for page_id, content_id, p_lines, page_num in page_entries:
        page_dict = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>"
        pdf_objs.append((page_id, page_dict))
        
        # Build stream commands
        stream_cmds = []
        
        # Top banner on first page or header on subsequent
        stream_cmds.append("q")
        if page_num == 1:
            # Header bar
            stream_cmds.append("0.1 0.2 0.5 rg") # Deep blue
            stream_cmds.append("40 730 532 30 re f")
            stream_cmds.append("1 1 1 rg") # White text
            stream_cmds.append("BT /F2 14 Tf 50 740 Td (INTER-COMPANY TRANSACTIONS FOR ERPNEXT) Tj ET")
            stream_cmds.append("0 0 0 rg") # Reset black
            y_start = 705
        else:
            # Subtle running header
            stream_cmds.append("0.4 0.4 0.4 rg")
            stream_cmds.append("BT /F1 9 Tf 40 760 Td (Inter-Company Transactions - User Guide & Tutorial) Tj ET")
            stream_cmds.append("0.8 0.8 0.8 RG 40 752 m 572 752 l S")
            stream_cmds.append("0 0 0 rg")
            y_start = 735

        # Running footer
        stream_cmds.append("0.4 0.4 0.4 rg")
        stream_cmds.append("0.8 0.8 0.8 RG 40 40 m 572 40 l S")
        stream_cmds.append(f"BT /F1 9 Tf 530 28 Td (Page {page_num} of {total_pages}) Tj ET")
        stream_cmds.append("0 0 0 rg")
        
        y = y_start
        for line in p_lines:
            if y < 55:
                break
            
            # Format headings vs body
            if line.startswith("# "):
                text = line[2:]
                stream_cmds.append(f"BT /F2 14 Tf 40 {y} Td ({text}) Tj ET")
                y -= 18
            elif line.startswith("## "):
                text = line[3:]
                stream_cmds.append(f"BT /F2 11 Tf 40 {y} Td ({text}) Tj ET")
                y -= 15
            elif line.startswith("### "):
                text = line[4:]
                stream_cmds.append(f"BT /F2 10 Tf 40 {y} Td ({text}) Tj ET")
                y -= 13
            elif line.startswith("* ") or line.startswith("- "):
                text = line[2:]
                stream_cmds.append(f"BT /F1 8.5 Tf 50 {y} Td (\\225 {text}) Tj ET")
                y -= 11.5
            elif line.startswith("   - ") or line.startswith("  * "):
                text = line[5:]
                stream_cmds.append(f"BT /F1 8.5 Tf 65 {y} Td (- {text}) Tj ET")
                y -= 11
            elif line.strip() == "---":
                stream_cmds.append(f"0.85 0.85 0.85 RG 40 {y} m 572 {y} l S 0 0 0 rg")
                y -= 10
            elif line.startswith("```"):
                y -= 4
            else:
                stream_cmds.append(f"BT /F1 8.5 Tf 40 {y} Td ({line}) Tj ET")
                y -= 11.5
                
        stream_cmds.append("Q")
        stream_data = "\n".join(stream_cmds).encode('latin-1', 'replace')
        content_dict = f"<< /Length {len(stream_data)} >>\nstream\n{stream_data.decode('latin-1')}\nendstream"
        pdf_objs.append((content_id, content_dict))

    # Sort objects by id
    pdf_objs.sort(key=lambda x: x[0])
    
    # Write PDF file with accurate xref table
    with open(output_path, "wb") as f:
        f.write(b"%PDF-1.4\n")
        offsets = {}
        for obj_id, obj_body in pdf_objs:
            offsets[obj_id] = f.tell()
            f.write(f"{obj_id} 0 obj\n{obj_body}\nendobj\n".encode('latin-1'))
            
        xref_offset = f.tell()
        total_objs = len(pdf_objs) + 1
        f.write(f"xref\n0 {total_objs}\n".encode('latin-1'))
        f.write(b"0000000000 65535 f \n")
        for obj_id in range(1, total_objs):
            pos = offsets.get(obj_id, 0)
            f.write(f"{pos:010d} 00000 n \n".encode('latin-1'))
            
        f.write(f"trailer\n<< /Size {total_objs} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode('latin-1'))

    print(f"Successfully generated User Guide PDF at {output_path} ({os.path.getsize(output_path)} bytes, {total_pages} pages)")

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/inter_company_transactions/inter_company_transactions/public/Inter_Company_Transactions_User_Guide.pdf"
    create_pdf(out)
