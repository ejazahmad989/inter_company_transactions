#!/usr/bin/env python3
"""
Brand Asset Generator for Inter-Company Transactions
Generates crisp, high-resolution PNG assets for Frappe Marketplace and Desk branding:
- inter_company_icon_512.png (512x512 App Icon)
- inter_company_logo.png (Horizontal brandmark)
- marketplace_banner.png (1280x640 Hero Banner)
"""

import math
import os
import shutil

from PIL import Image, ImageDraw, ImageFilter, ImageFont


def create_gradient_radial(width, height, center_x, center_y, max_radius, inner_color, outer_color):
    """Creates a radial gradient image."""
    base = Image.new("RGBA", (width, height), outer_color)
    # create radial mask
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    for r in range(int(max_radius), 0, -2):
        alpha = int(255 * (1 - (r / max_radius)))
        draw.ellipse([center_x - r, center_y - r, center_x + r, center_y + r], fill=alpha)

    top = Image.new("RGBA", (width, height), inner_color)
    base = Image.composite(top, base, mask)
    return base

def draw_squircle(draw, bounds, radius, fill, outline=None, width=1):
    """Draws a smooth rounded rectangle."""
    draw.rounded_rectangle(bounds, radius=radius, fill=fill, outline=outline, width=width)

def generate_app_icon_512(output_path):
    """Generates a high-precision 512x512 PNG app icon."""
    size = (512, 512)
    img = Image.new("RGBA", size, (0, 0, 0, 0))

    # 1. Background squircle with subtle gradient simulation
    bg_canvas = Image.new("RGBA", size, (15, 23, 42, 255)) # #0f172a
    bg_draw = ImageDraw.Draw(bg_canvas)

    # Gradient overlay: dark indigo at top right
    for y in range(512):
        ratio = y / 512.0
        r = int(15 * (1 - ratio) + 2 * ratio)
        g = int(23 * (1 - ratio) + 6 * ratio)
        b = int(60 * (1 - ratio) + 23 * ratio)
        bg_draw.line([(0, y), (512, y)], fill=(r, g, b, 255))

    # Mask to rounded squircle
    mask = Image.new("L", size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([16, 16, 496, 496], radius=108, fill=255)

    img.paste(bg_canvas, (0, 0), mask)

    draw = ImageDraw.Draw(img)
    # Outer border glow
    draw.rounded_rectangle([16, 16, 496, 496], radius=108, outline=(56, 189, 248, 180), width=3)

    # Subtle inner grid
    for x in range(96, 450, 80):
        draw.line([(x, 64), (x, 448)], fill=(255, 255, 255, 18), width=1)
    for y in range(96, 450, 80):
        draw.line([(64, y), (448, y)], fill=(255, 255, 255, 18), width=1)

    # Glowing center aura
    aura = Image.new("RGBA", size, (0, 0, 0, 0))
    aura_draw = ImageDraw.Draw(aura)
    aura_draw.ellipse([180 - 60, 256 - 60, 180 + 60, 256 + 60], fill=(37, 99, 235, 60))
    aura_draw.ellipse([332 - 60, 256 - 60, 332 + 60, 256 + 60], fill=(16, 185, 129, 60))
    aura = aura.filter(ImageFilter.GaussianBlur(20))
    img.alpha_composite(aura)

    draw = ImageDraw.Draw(img)

    # Flow curves:
    # Top arc (Company A -> Company B)
    draw.arc([170, 150, 342, 230], start=180, end=360, fill=(56, 189, 248, 240), width=6)
    draw.polygon([(348, 198), (348, 182), (360, 190)], fill=(52, 211, 153, 255))

    # Bottom arc (Company B -> Company A)
    draw.arc([170, 280, 342, 360], start=0, end=180, fill=(52, 211, 153, 240), width=6)
    draw.polygon([(164, 314), (164, 330), (152, 322)], fill=(56, 189, 248, 255))

    # Entity A (Hexagon)
    hex_a = [(176, 170), (236, 204), (236, 274), (176, 308), (116, 274), (116, 204)]
    draw.polygon(hex_a, fill=(15, 23, 42, 255), outline=(56, 189, 248, 255), width=7)
    # Building inside A
    draw.polygon([(148, 270), (148, 220), (176, 200), (204, 220), (204, 270)], fill=(30, 41, 59, 255), outline=(56, 189, 248, 255), width=3)
    draw.rectangle([160, 226, 170, 238], fill=(56, 189, 248, 255))
    draw.rectangle([182, 226, 192, 238], fill=(56, 189, 248, 255))
    draw.rectangle([160, 246, 170, 258], fill=(56, 189, 248, 255))
    draw.rectangle([182, 246, 192, 258], fill=(56, 189, 248, 255))

    # Entity B (Hexagon)
    hex_b = [(336, 170), (396, 204), (396, 274), (336, 308), (276, 274), (276, 204)]
    draw.polygon(hex_b, fill=(15, 23, 42, 255), outline=(52, 211, 153, 255), width=7)
    # Building inside B
    draw.polygon([(308, 270), (308, 220), (336, 200), (364, 220), (364, 270)], fill=(30, 41, 59, 255), outline=(52, 211, 153, 255), width=3)
    draw.rectangle([320, 226, 330, 238], fill=(52, 211, 153, 255))
    draw.rectangle([342, 226, 352, 238], fill=(52, 211, 153, 255))
    draw.rectangle([320, 246, 330, 258], fill=(52, 211, 153, 255))
    draw.rectangle([342, 246, 352, 258], fill=(52, 211, 153, 255))

    # Connecting central bridge
    draw.line([(236, 239), (276, 239)], fill=(99, 102, 241, 255), width=5)
    # Center circle
    draw.ellipse([256 - 28, 239 - 28, 256 + 28, 239 + 28], fill=(15, 23, 42, 255), outline=(129, 140, 248, 255), width=4)
    # Diamond
    draw.polygon([(256, 220), (274, 239), (256, 258), (238, 239)], fill=(255, 255, 255, 255))

    # Bottom badge
    draw.rounded_rectangle([116, 420, 396, 456], radius=18, fill=(30, 41, 59, 255), outline=(51, 65, 85, 255), width=2)
    # Text in badge
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    draw.text((256, 438), "ERPNEXT • v14 • v15 • v16", fill=(148, 163, 184, 255), anchor="mm", font=font)

    img.save(output_path, "PNG", optimize=True)
    print(f"Created {output_path}")

def generate_logo_png(output_path):
    """Generates a horizontal 720x160 logo PNG."""
    width, height = 720, 160
    img = Image.new("RGBA", (width, height), (15, 23, 42, 255))
    draw = ImageDraw.Draw(img)

    # Entity A
    hex_a = [(62, 48), (88, 63), (88, 97), (62, 112), (36, 97), (36, 63)]
    draw.polygon(hex_a, fill=(15, 23, 42, 255), outline=(56, 189, 248, 255), width=4)
    draw.polygon([(50, 96), (50, 72), (62, 62), (74, 72), (74, 96)], fill=(30, 41, 59, 255), outline=(56, 189, 248, 255), width=2)
    draw.rectangle([55, 76, 60, 82], fill=(56, 189, 248, 255))
    draw.rectangle([64, 76, 69, 82], fill=(56, 189, 248, 255))

    # Entity B
    hex_b = [(128, 48), (154, 63), (154, 97), (128, 112), (102, 97), (102, 63)]
    draw.polygon(hex_b, fill=(15, 23, 42, 255), outline=(52, 211, 153, 255), width=4)
    draw.polygon([(116, 96), (116, 72), (128, 62), (140, 72), (140, 96)], fill=(30, 41, 59, 255), outline=(52, 211, 153, 255), width=2)
    draw.rectangle([121, 76, 126, 82], fill=(52, 211, 153, 255))
    draw.rectangle([130, 76, 135, 82], fill=(52, 211, 153, 255))

    # Flow
    draw.arc([60, 38, 130, 75], start=180, end=360, fill=(56, 189, 248, 240), width=3)
    draw.arc([60, 85, 130, 122], start=0, end=180, fill=(52, 211, 153, 240), width=3)

    # Nexus
    draw.ellipse([95 - 14, 80 - 14, 95 + 14, 80 + 14], fill=(15, 23, 42, 255), outline=(129, 140, 248, 255), width=2)
    draw.polygon([(95, 71), (103, 80), (95, 89), (87, 80)], fill=(255, 255, 255, 255))

    # Typography
    font = ImageFont.load_default()
    draw.text((185, 42), "INTER-COMPANY", fill=(255, 255, 255, 255), font=font)
    draw.text((185, 72), "TRANSACTIONS", fill=(56, 189, 248, 255), font=font)

    # Pill
    draw.rounded_rectangle([185, 110, 560, 136], radius=13, fill=(30, 41, 59, 255), outline=(51, 65, 85, 255), width=1)
    draw.ellipse([196, 119, 204, 127], fill=(16, 185, 129, 255))
    draw.text((212, 118), "FOR ERPNEXT v14 • v15 • v16 (READY)", fill=(148, 163, 184, 255), font=font)

    img.save(output_path, "PNG", optimize=True)
    print(f"Created {output_path}")

def generate_marketplace_banner_png(output_path):
    """Generates a 1280x640 banner PNG."""
    width, height = 1280, 640
    img = Image.new("RGBA", (width, height), (9, 13, 22, 255))
    draw = ImageDraw.Draw(img)

    # Gradient background
    for y in range(height):
        ratio = y / height
        r = int(9 * (1 - ratio) + 15 * ratio)
        g = int(13 * (1 - ratio) + 23 * ratio)
        b = int(22 * (1 - ratio) + 45 * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    font = ImageFont.load_default()

    # App icon square
    draw.rounded_rectangle([80, 80, 240, 240], radius=32, fill=(15, 23, 42, 255), outline=(56, 189, 248, 200), width=3)
    draw.text((160, 160), "ICT", fill=(56, 189, 248, 255), anchor="mm", font=font)

    # App Title & Subtitle
    draw.text((270, 95), "Inter-Company Transactions", fill=(255, 255, 255, 255), font=font)
    draw.text((270, 135), "Autonomous Mirroring, Transfer Pricing & Multi-Site Sync for ERPNext", fill=(56, 189, 248, 255), font=font)

    # Certification Pill
    draw.rounded_rectangle([270, 175, 680, 215], radius=20, fill=(16, 185, 129, 40), outline=(16, 185, 129, 255), width=2)
    draw.text((290, 188), "✓ OFFICIALLY CERTIFIED FOR ERPNEXT v14 • v15 • v16", fill=(52, 211, 153, 255), font=font)

    # 4 Feature Cards
    cards = [
        (80, 270, 265, "Auto-Mirroring", ["• Sales Order <-> Purchase Order", "• Sales Inv <-> Purchase Inv", "• Delivery Note <-> Purchase Rec"]),
        (375, 270, 265, "Transfer Pricing", ["• Cost-Plus, Resale, Price Lists", "• Multi-currency FX rules", "• Arm's-length OECD compliance"]),
        (670, 270, 265, "Multi-Site Sync", ["• Cross-server REST federation", "• HMAC-SHA256 signatures", "• Real-time ping & firewall test"]),
        (965, 270, 235, "Netting & Elim", ["• Bilateral & Multilateral netting", "• Auto elimination journals", "• Dispute triage & credit notes"]),
    ]

    for x, y, w, title, bullets in cards:
        draw.rounded_rectangle([x, y, x + w, y + 170], radius=16, fill=(30, 41, 59, 220), outline=(56, 189, 248, 80), width=1)
        draw.text((x + 20, y + 25), title, fill=(255, 255, 255, 255), font=font)
        curr_y = y + 65
        for bullet in bullets:
            draw.text((x + 20, curr_y), bullet, fill=(148, 163, 184, 255), font=font)
            curr_y += 26

    # Trust bar
    draw.rounded_rectangle([80, 475, 1200, 565], radius=20, fill=(11, 17, 32, 255), outline=(30, 41, 59, 255), width=2)
    draw.text((120, 515), "★ Frappe Marketplace Ready", fill=(56, 189, 248, 255), font=font)
    draw.text((470, 515), "✓ 100% Native Frappe Python Backend (No Core Hacks)", fill=(52, 211, 153, 255), font=font)
    draw.text((920, 515), "🌍 English, Français, Español, العربية", fill=(129, 140, 248, 255), font=font)

    img.save(output_path, "PNG", optimize=True)
    print(f"Created {output_path}")

def sync_assets_to_all_paths():
    """Copies all generated assets to root and package asset paths for compatibility."""
    src_dir = "inter_company_transactions/public/images"
    dest_dirs = ["public/images", "assets/images"]

    for dest in dest_dirs:
        os.makedirs(dest, exist_ok=True)
        for item in os.listdir(src_dir):
            s = os.path.join(src_dir, item)
            d = os.path.join(dest, item)
            if os.path.isfile(s):
                shutil.copy2(s, d)
                print(f"Synced {item} -> {dest}/")

if __name__ == "__main__":
    os.makedirs("inter_company_transactions/public/images", exist_ok=True)
    generate_app_icon_512("inter_company_transactions/public/images/inter_company_icon_512.png")
    generate_logo_png("inter_company_transactions/public/images/inter_company_logo.png")
    generate_marketplace_banner_png("inter_company_transactions/public/images/marketplace_banner.png")
    sync_assets_to_all_paths()
    print("All brand assets successfully generated and synced!")
