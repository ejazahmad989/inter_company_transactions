#!/usr/bin/env python3
"""
Generate a richly illustrated, beginner-friendly Visual Workbook PDF
("Inter_Company_Transactions_Visual_Workbook.pdf") embedding the real
ERPNext workflow screenshots from /screenshots/.

Usage:
    python3 inter_company_transactions/generate_visual_workbook.py
"""

import base64
import shutil
from pathlib import Path


def img_data_uri(screenshots_dir: Path, filename: str) -> str:
    img_path = screenshots_dir / filename
    if not img_path.exists():
        raise FileNotFoundError(f"Missing screenshot: {img_path}")
    b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def build_html(screenshots_dir: Path, logo_svg_path: Path | None = None) -> str:
    imgs = {
        "main_coa": img_data_uri(screenshots_dir, "main_coa.png"),
        "abc_coa": img_data_uri(screenshots_dir, "abc_coa.png"),
        "john_coa": img_data_uri(screenshots_dir, "john_coa.png"),
        "tx_link": img_data_uri(screenshots_dir, "transaction_link.png"),
        "tx_link_a": img_data_uri(screenshots_dir, "transaction_link_A.png"),
        "tx_link_other": img_data_uri(screenshots_dir, "transaction_link_other_company_settings.png"),
        "tx_types": img_data_uri(screenshots_dir, "transaction_link_Transaction_type.png"),
        "so_form": img_data_uri(screenshots_dir, "S-order-same_currency.png"),
        "so_msg": img_data_uri(screenshots_dir, "sales_order_msg.png"),
        "po_mirror": img_data_uri(screenshots_dir, "p-order_mirror_entry_created.png"),
        "je_form": img_data_uri(screenshots_dir, "journal_entry.png"),
        "je_msg": img_data_uri(screenshots_dir, "journal_entry_msg.png"),
        "je_mirror": img_data_uri(screenshots_dir, "journal_entry_mirror.png"),
        "pe_form": img_data_uri(screenshots_dir, "payment_entry.png"),
        "pe_msg": img_data_uri(screenshots_dir, "payment_entry_msg.png"),
        "pe_mirror": img_data_uri(screenshots_dir, "payment_entry_mirror_entry.png"),
    }

    logo_block = ""
    if logo_svg_path and logo_svg_path.exists():
        svg_b64 = base64.b64encode(logo_svg_path.read_bytes()).decode("ascii")
        logo_block = (
            '<div style="display:inline-block;background:#0f172a;padding:10px 16px;'
            'border-radius:10px;margin-bottom:14px;">'
            f'<img src="data:image/svg+xml;base64,{svg_b64}" alt="Logo" style="height:46px;display:block;" />'
            "</div>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>Inter-Company Transactions — Visual Step-by-Step Workbook</title>
<style>
  @page {{
    size: A4;
    margin: 14mm 14mm 16mm 14mm;
  }}
  * {{
    box-sizing: border-box;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    line-height: 1.48;
    font-size: 10.5pt;
    margin: 0;
    padding: 0;
  }}
  .page-break {{
    page-break-before: always;
  }}
  .avoid-break {{
    page-break-inside: avoid;
    break-inside: avoid;
  }}

  /* Cover */
  .cover {{
    border: 2px solid #cbd5e1;
    border-radius: 14px;
    padding: 28px 30px;
    background: linear-gradient(155deg, #f8fafc 0%, #eef2ff 55%, #ecfeff 100%);
    min-height: 245mm;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }}
  .cover-badge {{
    display: inline-block;
    background: #1d4ed8;
    color: #fff;
    font-weight: 700;
    font-size: 9pt;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 5px 12px;
    border-radius: 6px;
    margin-bottom: 14px;
  }}
  .cover h1 {{
    font-size: 25pt;
    line-height: 1.15;
    color: #0f172a;
    margin: 0 0 10px 0;
  }}
  .cover .subtitle {{
    font-size: 12.5pt;
    color: #334155;
    margin: 0 0 22px 0;
  }}
  .cast-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin: 18px 0;
  }}
  .cast-card {{
    background: #ffffff;
    border: 1.5px solid #cbd5e1;
    border-radius: 10px;
    padding: 12px;
  }}
  .cast-card.main {{ border-top: 5px solid #2563eb; }}
  .cast-card.abc  {{ border-top: 5px solid #059669; }}
  .cast-card.john {{ border-top: 5px solid #d97706; }}
  .cast-title {{
    font-weight: 700;
    font-size: 11pt;
    margin-bottom: 4px;
  }}
  .cast-sub {{
    font-size: 9pt;
    color: #475569;
  }}
  .toc-box {{
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 14px 18px;
    margin-top: 12px;
  }}
  .toc-box h3 {{
    margin: 0 0 8px 0;
    font-size: 11pt;
    color: #1d4ed8;
  }}
  .toc-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px 18px;
    font-size: 9.5pt;
  }}
  .cover-footer {{
    border-top: 1px solid #cbd5e1;
    padding-top: 12px;
    font-size: 9pt;
    color: #475569;
    display: flex;
    justify-content: space-between;
  }}

  /* Chapter headers */
  .lesson-header {{
    background: #0f172a;
    color: #ffffff;
    padding: 12px 16px;
    border-radius: 10px;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .lesson-num {{
    background: #3b82f6;
    color: #ffffff;
    font-weight: 800;
    font-size: 11pt;
    padding: 6px 11px;
    border-radius: 7px;
    white-space: nowrap;
  }}
  .lesson-title {{
    margin: 0;
    font-size: 14pt;
    line-height: 1.25;
  }}
  .lesson-desc {{
    margin: 2px 0 0 0;
    font-size: 9.5pt;
    color: #cbd5e1;
  }}

  /* Kid-friendly boxes */
  .kid-box {{
    background: #eff6ff;
    border-left: 5px solid #2563eb;
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    margin: 10px 0 14px 0;
    page-break-inside: avoid;
    break-inside: avoid;
  }}
  .kid-box.green {{
    background: #ecfdf5;
    border-left-color: #059669;
  }}
  .kid-box.amber {{
    background: #fffbeb;
    border-left-color: #d97706;
  }}
  .kid-box.rose {{
    background: #fff1f2;
    border-left-color: #e11d48;
  }}
  .kid-box strong.label {{
    display: block;
    font-size: 10pt;
    margin-bottom: 3px;
    color: #0f172a;
  }}

  /* Entity pills */
  .pill {{
    display: inline-block;
    padding: 1px 7px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 9pt;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }}
  .pill-main {{ background: #dbeafe; color: #1e40af; }}
  .pill-abc  {{ background: #d1fae5; color: #065f46; }}
  .pill-john {{ background: #fef3c7; color: #92400e; }}
  .pill-tmp  {{ background: #f3e8ff; color: #6b21a8; }}

  /* Screenshot frames */
  .shot-card {{
    border: 1.5px solid #cbd5e1;
    border-radius: 10px;
    overflow: hidden;
    background: #ffffff;
    margin: 10px 0 14px 0;
    page-break-inside: avoid;
    break-inside: avoid;
  }}
  .shot-head {{
    background: #f1f5f9;
    padding: 7px 12px;
    border-bottom: 1px solid #cbd5e1;
    font-weight: 700;
    font-size: 9.5pt;
    color: #0f172a;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .shot-tag {{
    font-size: 8.5pt;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
    background: #e2e8f0;
    color: #334155;
  }}
  .shot-card img {{
    width: 100%;
    height: auto;
    display: block;
    border-bottom: 1px solid #e2e8f0;
  }}
  .shot-caption {{
    padding: 9px 12px;
    font-size: 9.5pt;
    background: #ffffff;
  }}
  .shot-caption ul {{
    margin: 4px 0 0 16px;
    padding: 0;
  }}
  .shot-caption li {{
    margin-bottom: 3px;
  }}

  /* Diagrams & Tables */
  .diagram-box {{
    border: 1.5px dashed #94a3b8;
    border-radius: 10px;
    padding: 12px 14px;
    background: #f8fafc;
    margin: 10px 0 14px 0;
    page-break-inside: avoid;
    break-inside: avoid;
  }}
  .two-col {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }}
  .col-card {{
    background: #ffffff;
    border: 1.5px solid #cbd5e1;
    border-radius: 8px;
    padding: 10px 12px;
  }}
  .col-card h4 {{
    margin: 0 0 6px 0;
    font-size: 10pt;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0 12px 0;
    font-size: 9.2pt;
    page-break-inside: avoid;
    break-inside: avoid;
  }}
  th {{
    background: #1e293b;
    color: #ffffff;
    text-align: left;
    padding: 7px 9px;
    font-weight: 700;
  }}
  td {{
    border: 1px solid #cbd5e1;
    padding: 6px 9px;
    vertical-align: top;
  }}
  tr:nth-child(even) td {{
    background: #f8fafc;
  }}
  .step-num {{
    display: inline-block;
    width: 20px;
    height: 20px;
    line-height: 20px;
    text-align: center;
    background: #2563eb;
    color: #ffffff;
    border-radius: 50%;
    font-weight: 800;
    font-size: 9pt;
    margin-right: 5px;
  }}
  h3 {{
    margin: 12px 0 6px 0;
    color: #0f172a;
    font-size: 11.5pt;
  }}
</style>
</head>
<body>

<!-- ==================== COVER PAGE ==================== -->
<div class="cover">
  <div>
    {logo_block}
    <div class="cover-badge">Visual Step-by-Step Workbook &bull; ERPNext v15 &amp; v16</div>
    <h1>Inter-Company Transactions<br/>Made Simple</h1>
    <p class="subtitle">
      A picture-by-picture guide explaining <strong>TMP Clearing Accounts</strong>,
      <strong>Main vs. Other Company Links</strong>, <strong>Customer &harr; Supplier Mirroring</strong>,
      <strong>Transit Warehouses</strong>, and live document automation — using real ERPNext screens.
    </p>

    <div class="cast-grid">
      <div class="cast-card main">
        <div class="cast-title"><span class="pill pill-main">MAIN (AM)</span></div>
        <div class="cast-sub">
          <strong>Hub / Main Company</strong><br/>
          Currency: PKR<br/>
          Clearing Accounts:<br/>
          &bull; <code>TMP-ACB-IC - AM</code> (for ABC)<br/>
          &bull; <code>TMP-JOHN-IC - AM</code> (for John)<br/>
          Transit WH: <code>Goods In Transit - AM</code>
        </div>
      </div>
      <div class="cast-card abc">
        <div class="cast-title"><span class="pill pill-abc">ABC Company (AC)</span></div>
        <div class="cast-sub">
          <strong>Sister Company #1</strong><br/>
          Currency: PKR<br/>
          Clearing Account:<br/>
          &bull; <code>TMP-MAIN - AC</code> (for MAIN)<br/>
          Party names in ABC:<br/>
          &bull; <code>Main Customer (ABC)</code><br/>
          &bull; <code>Main Supplier (ABC)</code><br/>
          Transit WH: <code>Goods In Transit - AC</code>
        </div>
      </div>
      <div class="cast-card john">
        <div class="cast-title"><span class="pill pill-john">John Company (JC)</span></div>
        <div class="cast-sub">
          <strong>Sister Company #2</strong><br/>
          Currency: USD ($)<br/>
          Clearing Account:<br/>
          &bull; <code>TMP-MAIN - JC</code> (for MAIN)<br/>
          Separate currency &amp; separate bridge account from ABC!
        </div>
      </div>
    </div>

    <div class="toc-box">
      <h3>What You Will Master in This Workbook</h3>
      <div class="toc-grid">
        <div><strong>Lesson 1:</strong> The 30-Second "Family Pockets" Idea</div>
        <div><strong>Lesson 5:</strong> Journal Entry Mirroring (Credit &harr; Debit Flip)</div>
        <div><strong>Lesson 2:</strong> What Every <code>TMP-*</code> Account Does (3 COAs)</div>
        <div><strong>Lesson 6:</strong> Payment Entry Mirroring (Receive &harr; Pay)</div>
        <div><strong>Lesson 3:</strong> Inside Intercompany Transaction Link &amp; Warehouses</div>
        <div><strong>Lesson 7:</strong> Golden Cheat Sheet &amp; Volume 2 Picture Checklist</div>
        <div><strong>Lesson 4:</strong> Live Sales Order &rarr; Purchase Order Walk-Through</div>
        <div>&nbsp;</div>
      </div>
    </div>
  </div>

  <div class="cover-footer">
    <span><strong>Publisher:</strong> Ejaz Tech (<code>ejazahmad989@gmail.com</code>) &amp; Rahil Ali</span>
    <span><strong>App:</strong> <code>inter_company_transactions</code> (v1.0.0)</span>
  </div>
</div>

<!-- ==================== LESSON 1 ==================== -->
<div class="page-break"></div>
<div class="lesson-header">
  <div class="lesson-num">LESSON 1</div>
  <div>
    <h2 class="lesson-title">The Big Idea: Why Two Sister Companies Need a Mirror</h2>
    <p class="lesson-desc">Think of one business family with separate wallets and books.</p>
  </div>
</div>

<div class="kid-box">
  <strong class="label">Explain It Simply: The Two-Pocket Rule</strong>
  Imagine you own two shops: <strong>MAIN</strong> (Shop A) and <strong>ABC Company</strong> (Shop B).
  Legally, each shop keeps its own ERPNext books, taxes, and stock.
  When Shop A sells goods to Shop B:
  <br/>&bull; Shop A writes a <strong>Sales Order</strong> (I am selling to ABC!).
  <br/>&bull; Shop B must write a <strong>Purchase Order</strong> (I am buying from MAIN!).
  <br/>Without this app, staff must type every order, invoice, journal, and payment <strong>twice</strong>.
  With <strong>Inter-Company Transactions</strong>, you type it <strong>once</strong> in Shop A, click Submit, and Shop B's matching Draft appears automatically!
</div>

<div class="diagram-box">
  <h3 style="margin-top:0;">How Automatic Mirroring Works in 3 Steps</h3>
  <svg viewBox="0 0 760 140" width="100%" xmlns="http://www.w3.org/2000/svg" style="font-family:sans-serif;">
    <rect x="10" y="20" width="215" height="96" rx="10" fill="#dbeafe" stroke="#2563eb" stroke-width="2"/>
    <text x="117" y="45" text-anchor="middle" font-size="13" font-weight="bold" fill="#1e3a8a">1. MAIN (Seller / Sender)</text>
    <text x="117" y="66" text-anchor="middle" font-size="11" fill="#1e293b">Select Customer: ABC Customer</text>
    <text x="117" y="84" text-anchor="middle" font-size="11" fill="#1e293b">App auto-ticks: Is Intercompany</text>
    <text x="117" y="102" text-anchor="middle" font-size="11" font-weight="bold" fill="#1d4ed8">User clicks Submit</text>

    <line x1="230" y1="68" x2="275" y2="68" stroke="#2563eb" stroke-width="3"/>
    <polygon points="275,61 290,68 275,75" fill="#2563eb"/>

    <rect x="292" y="20" width="176" height="96" rx="10" fill="#f3e8ff" stroke="#7c3aed" stroke-width="2"/>
    <text x="380" y="47" text-anchor="middle" font-size="12" font-weight="bold" fill="#5b21b6">2. Inter-Company Engine</text>
    <text x="380" y="68" text-anchor="middle" font-size="10.5" fill="#1e293b">Reads Transaction Link</text>
    <text x="380" y="85" text-anchor="middle" font-size="10.5" fill="#1e293b">Flips Party &amp; Debit/Credit</text>
    <text x="380" y="102" text-anchor="middle" font-size="10.5" fill="#5b21b6">Logs Document Reference</text>

    <line x1="473" y1="68" x2="518" y2="68" stroke="#059669" stroke-width="3"/>
    <polygon points="518,61 533,68 518,75" fill="#059669"/>

    <rect x="535" y="20" width="215" height="96" rx="10" fill="#d1fae5" stroke="#059669" stroke-width="2"/>
    <text x="642" y="45" text-anchor="middle" font-size="13" font-weight="bold" fill="#065f46">3. ABC Company (Receiver)</text>
    <text x="642" y="66" text-anchor="middle" font-size="11" fill="#1e293b">Gets Draft Purchase / Receipt</text>
    <text x="642" y="84" text-anchor="middle" font-size="11" fill="#1e293b">Uses: Main Supplier (ABC)</text>
    <text x="642" y="102" text-anchor="middle" font-size="11" font-weight="bold" fill="#047857">Price Locked &bull; Warehouse Editable</text>
  </svg>
</div>

<!-- ==================== LESSON 2 ==================== -->
<div class="lesson-header" style="margin-top:8px;">
  <div class="lesson-num">LESSON 2</div>
  <div>
    <h2 class="lesson-title">Chart of Accounts: What Are All Those <code>TMP-*</code> Accounts For?</h2>
    <p class="lesson-desc">Understanding <code>TMP-ACB-IC - AM</code>, <code>TMP-JOHN-IC - AM</code>, <code>TMP-MAIN - AC</code>, and <code>TMP-MAIN - JC</code>.</p>
  </div>
</div>

<div class="kid-box amber">
  <strong class="label">Why Do We Need a <code>TMP</code> Account at All? (The "Unknown Bank" Puzzle)</strong>
  In accounting, every <strong>Journal Entry</strong> or <strong>Payment Entry</strong> MUST have <strong>two sides</strong>:
  a Debit and a Credit (or <em>Paid From</em> and <em>Paid To</em>).
  <br/><br/>
  Suppose <span class="pill pill-main">MAIN</span> pays <strong>Cash</strong> and records:
  <em>Debit ABC Customer Rs. 100 / Credit Cash - AM Rs. 100</em>.
  Now the app creates the mirror entry inside <span class="pill pill-abc">ABC Company</span>.
  ABC knows one side: <em>Main Supplier (ABC)</em>.
  <strong>But which bank or cash box inside ABC Company should hold the other side?</strong>
  MAIN doesn't know ABC's local cash box! So the app safely puts the second line into ABC's dedicated
  <strong>Inter-Company Clearing ("Bridge") Account</strong>: <span class="pill pill-tmp">TMP-MAIN - AC</span>!
</div>

<div class="diagram-box">
  <h3 style="margin-top:0;">One Dedicated Walkie-Talkie Channel Per Sister Pair</h3>
  <table>
    <thead>
      <tr>
        <th>Company</th>
        <th>Clearing Account in Chart of Accounts</th>
        <th>Who It Talks To</th>
        <th>Why Separate Accounts?</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><span class="pill pill-main">MAIN</span></td>
        <td><code>TMP-ACB-IC - AM</code><br/><code>TMP-JOHN-IC - AM</code></td>
        <td>&rarr; <strong>ABC Company</strong><br/>&rarr; <strong>John Company</strong></td>
        <td>MAIN trades with <strong>two</strong> sisters, so MAIN keeps two separate bridge buckets so ABC's and John's numbers never mix!</td>
      </tr>
      <tr>
        <td><span class="pill pill-abc">ABC Company</span></td>
        <td><code>TMP-MAIN - AC</code></td>
        <td>&rarr; <strong>MAIN</strong></td>
        <td>Used whenever MAIN creates a mirrored Journal Entry or Payment Entry inside ABC Company.</td>
      </tr>
      <tr>
        <td><span class="pill pill-john">John Company</span></td>
        <td><code>TMP-MAIN - JC</code></td>
        <td>&rarr; <strong>MAIN</strong></td>
        <td>Used whenever MAIN creates a mirrored Journal Entry or Payment Entry inside John Company (USD ledger).</td>
      </tr>
    </tbody>
  </table>
  <p style="margin:4px 0 0 0;font-size:9pt;color:#475569;">
    <strong>Important Note:</strong> Notice <code>Temporary Opening - AM / AC / JC</code> already comes built into standard ERPNext for opening balances — leave it alone! Only <code>TMP-&lt;Partner&gt;</code> accounts are your inter-company bridges (and for Payment Entries, the app checks/sets them as <em>Bank</em> or <em>Cash</em> type so Payment Entry saves cleanly). Before submitting the mirrored Draft, ABC's accountant can either keep <code>TMP-MAIN - AC</code> or switch that line to ABC's real Bank/Cash account!
  </p>
</div>

<div class="shot-card">
  <div class="shot-head">
    <span><span class="step-num">1</span> MAIN Company Chart of Accounts — Two Bridge Accounts</span>
    <span class="shot-tag">screenshots/main_coa.png</span>
  </div>
  <img src="{imgs['main_coa']}" alt="MAIN Chart of Accounts" />
  <div class="shot-caption">
    Under <strong>Temporary Accounts - AM</strong>, MAIN has <code>TMP-ACB-IC - AM</code> (dedicated to ABC Company) and <code>TMP-JOHN-IC - AM</code> (dedicated to John Company). Right now both show <strong>Rs 0.00</strong> because clearing accounts zero out once settled or reclassified!
  </div>
</div>

<div class="page-break"></div>

<div class="two-col">
  <div class="shot-card" style="margin-top:0;">
    <div class="shot-head">
      <span><span class="step-num">2</span> ABC Company COA</span>
      <span class="shot-tag">abc_coa.png</span>
    </div>
    <img src="{imgs['abc_coa']}" alt="ABC Chart of Accounts" />
    <div class="shot-caption">
      Under <strong>Temporary Accounts - AC</strong>, ABC Company holds <code>TMP-MAIN - AC</code> exclusively for transactions with MAIN.
    </div>
  </div>
  <div class="shot-card" style="margin-top:0;">
    <div class="shot-head">
      <span><span class="step-num">3</span> John Company COA</span>
      <span class="shot-tag">john_coa.png</span>
    </div>
    <img src="{imgs['john_coa']}" alt="John Chart of Accounts" />
    <div class="shot-caption">
      Under <strong>Temporary Accounts - JC</strong>, John Company holds <code>TMP-MAIN - JC</code> in <strong>USD ($)</strong> for transactions with MAIN.
    </div>
  </div>
</div>

<!-- ==================== LESSON 3 ==================== -->
<div class="lesson-header">
  <div class="lesson-num">LESSON 3</div>
  <div>
    <h2 class="lesson-title">Intercompany Transaction Link: Where Every Setting Goes &amp; Why</h2>
    <p class="lesson-desc">Master Main vs. Other Company fields, Customer &harr; Supplier pairing, and Transit Warehouses.</p>
  </div>
</div>

<div class="kid-box green">
  <strong class="label">The Golden Rule of "My Customer = Your Supplier"</strong>
  Think about two people on a phone call:
  <br/>&bull; When <strong>MAIN sells</strong> to ABC Company, MAIN calls ABC <strong>"ABC Customer"</strong> (<code>Main Company Customer</code>).
  <br/>&bull; On the same deal, ABC Company is <strong>buying</strong> from MAIN, so ABC calls MAIN <strong>"Main Supplier (ABC)"</strong> (<code>Other Company Supplier</code>)!
  <br/>&bull; And in reverse, when <strong>ABC sells</strong> to MAIN: ABC uses <code>Other Company Customer</code> (<strong>Main Customer (ABC)</strong>) &harr; MAIN uses <code>Main Company Supplier</code> (<strong>ABC Supplier</strong>).
</div>

<div class="diagram-box">
  <h3 style="margin-top:0;">Exact Field-by-Field Map (From Your Screenshots)</h3>
  <table>
    <thead>
      <tr>
        <th style="width:24%;">Section &amp; Field</th>
        <th style="width:22%;">Value in Your Setup</th>
        <th style="width:54%;">What It Means in Plain English</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Main Company</strong> (Header)</td>
        <td><span class="pill pill-main">MAIN</span></td>
        <td>Put your <strong>hub / primary company</strong> here. One Link document connects MAIN to its sister companies.</td>
      </tr>
      <tr>
        <td><strong>Sister Company</strong> (Header)</td>
        <td><span class="pill pill-abc">ABC Company</span></td>
        <td><strong>Read-only!</strong> Auto-filled by the app from Row #1 of <em>Linked Companies</em> below.</td>
      </tr>
      <tr>
        <td><strong>Row &rarr; Company *</strong></td>
        <td><span class="pill pill-abc">ABC Company</span></td>
        <td>Put the <strong>partner / other company</strong> name here (never MAIN).</td>
      </tr>
      <tr>
        <td><strong>Main Company Customer</strong></td>
        <td><code>ABC Customer</code></td>
        <td>Customer record inside <strong>MAIN</strong> (used when MAIN sells to ABC). Pairs with <code>Other Company Supplier</code>.</td>
      </tr>
      <tr>
        <td><strong>Main Company Supplier</strong></td>
        <td><code>ABC Supplier</code></td>
        <td>Supplier record inside <strong>MAIN</strong> (used when MAIN buys from ABC). Pairs with <code>Other Company Customer</code>.</td>
      </tr>
      <tr>
        <td><strong>Main Company Account</strong></td>
        <td><code>TMP-ACB-IC - AM</code></td>
        <td>Clearing bridge inside <strong>MAIN</strong> for Journal &amp; Payment entries from ABC.</td>
      </tr>
      <tr>
        <td><strong>Main Company Transit WH</strong></td>
        <td><code>Goods In Transit - AM</code></td>
        <td>Warehouse inside <strong>MAIN</strong> where stock lands when <strong>ABC transfers stock TO MAIN</strong>.</td>
      </tr>
      <tr>
        <td><strong>Other Company Customer</strong></td>
        <td><code>Main Customer (ABC)</code></td>
        <td>Customer record inside <strong>ABC Company</strong> (used when ABC sells to MAIN).</td>
      </tr>
      <tr>
        <td><strong>Other Company Supplier</strong></td>
        <td><code>Main Supplier (ABC)</code></td>
        <td>Supplier record inside <strong>ABC Company</strong> (used when ABC buys from MAIN — mirrors <code>ABC Customer</code>).</td>
      </tr>
      <tr>
        <td><strong>Other Company Account</strong></td>
        <td><code>TMP-MAIN - AC</code></td>
        <td>Clearing bridge inside <strong>ABC Company</strong> for Journal &amp; Payment entries from MAIN.</td>
      </tr>
      <tr>
        <td><strong>Other Company Transit WH</strong></td>
        <td><code>Goods In Transit - AC</code></td>
        <td>Warehouse inside <strong>ABC Company</strong> where stock lands when <strong>MAIN transfers stock TO ABC</strong>.</td>
      </tr>
    </tbody>
  </table>
</div>

<div class="kid-box" style="margin-top:8px;padding:8px 12px;">
  <strong class="label">How Do Transit Warehouses Actually Work?</strong>
  In ERPNext, Company B is <strong>never allowed</strong> to use Company A's warehouse directly (<em>"Warehouse does not belong to company"</em>).
  When <span class="pill pill-main">MAIN</span> submits a <strong>Stock Entry (Material Issue)</strong> to a <strong>Same-Currency sister company</strong> (e.g., <code>PKR &rarr; PKR</code>), the engine strips MAIN's source warehouse and drops the stock into <span class="pill pill-abc">ABC Company</span>'s
  <strong>Other Company Transit Warehouse</strong> (<code>Goods In Transit - AC</code>) as a Draft <strong>Material Receipt</strong>.
  <em>(Stock Entry only works for Same-Currency companies. For different currencies such as <code>PKR &harr; USD</code>, use <strong>Delivery Note &rarr; Purchase Receipt</strong> or <strong>Sales Invoice &rarr; Purchase Invoice</strong>!)</em>
</div>

<div class="page-break"></div>

<div class="shot-card">
  <div class="shot-head">
    <span><span class="step-num">4</span> Intercompany Transaction Link — Main Header &amp; Automation Switches</span>
    <span class="shot-tag">screenshots/transaction_link.png</span>
  </div>
  <img src="{imgs['tx_link']}" alt="Intercompany Transaction Link" />
  <div class="shot-caption">
    <ul>
      <li><strong>Top:</strong> <code>Main Company = MAIN</code>, auto-resolved <code>Sister Company = ABC Company</code>, and <strong>Preload Transaction Types</strong> button at top-right.</li>
      <li><strong>Automation Settings:</strong> Keep <code>Auto Create Linked Document as Draft</code> checked so the other company reviews warehouses/accounts before submitting, and <code>Auto Cancel Linked Document</code> checked so cancelling in MAIN cleanly cancels ABC's mirror.</li>
    </ul>
  </div>
</div>

<div class="two-col">
  <div class="shot-card" style="margin-top:0;">
    <div class="shot-head">
      <span><span class="step-num">5</span> Row Edit: Main Company Settings</span>
      <span class="shot-tag">transaction_link_A.png</span>
    </div>
    <img src="{imgs['tx_link_a']}" alt="Main Company Settings inside Row" />
    <div class="shot-caption">
      Both Transit Warehouses (<code>Goods In Transit - AM</code> &amp; <code>Goods In Transit - AC</code>) plus MAIN's party &amp; clearing account settings (<code>ABC Customer</code>, <code>ABC Supplier</code>, <code>TMP-ACB-IC - AM</code>).
    </div>
  </div>
  <div class="shot-card" style="margin-top:0;">
    <div class="shot-head">
      <span><span class="step-num">6</span> Row Edit: Other Company Settings</span>
      <span class="shot-tag">transaction_link_other_company_settings.png</span>
    </div>
    <img src="{imgs['tx_link_other']}" alt="Other Company Settings inside Row" />
    <div class="shot-caption">
      Scroll down inside the same row modal to map ABC Company's side: <code>Main Customer (ABC)</code>, <code>Main Supplier (ABC)</code>, and <code>TMP-MAIN - AC</code>.
    </div>
  </div>
</div>

<div class="shot-card">
  <div class="shot-head">
    <span><span class="step-num">7</span> Supported Transaction Types Table (All 16 Bidirectional Pairs)</span>
    <span class="shot-tag">screenshots/transaction_link_Transaction_type.png</span>
  </div>
  <img src="{imgs['tx_types']}" alt="Transaction Types Table" />
  <div class="shot-caption">
    Click <strong>+ Populate All Supported Types</strong> once to fill all 16 pairs automatically: Sales Order &harr; Purchase Order, Sales Invoice &harr; Purchase Invoice, Delivery Note &harr; Purchase Receipt, Quotation &harr; Supplier Quotation, Material Request, RFQ, Stock Entry, Journal Entry, Payment Entry, and Landed Cost Voucher &rarr; Journal Entry.
  </div>
</div>

<!-- ==================== LESSON 4 ==================== -->
<div class="page-break"></div>
<div class="lesson-header">
  <div class="lesson-num">LESSON 4</div>
  <div>
    <h2 class="lesson-title">Live Walk-Through #1: Sales Order &rarr; Mirrored Purchase Order</h2>
    <p class="lesson-desc">Watch <code>SAL-ORD-2026-00012</code> in MAIN automatically create <code>PUR-ORD-2026-00011</code> in ABC Company.</p>
  </div>
</div>

<div class="shot-card">
  <div class="shot-head">
    <span><span class="step-num">1</span> Create Sales Order in MAIN &mdash; Pick <code>ABC Customer</code></span>
    <span class="shot-tag">screenshots/S-order-same_currency.png</span>
  </div>
  <img src="{imgs['so_form']}" alt="Sales Order Auto-Detection" />
  <div class="shot-caption">
    As soon as you choose <strong>Customer = ABC Customer</strong>, you do <em>not</em> need to touch any checkbox: the app automatically ticks <strong>Is Intercompany</strong> and fills <strong>Intercompany Target Company = ABC Company</strong>! Item: <em>Dairy America</em>, Qty <code>1.000</code>, Rate <code>Rs 46,000.00</code>.
  </div>
</div>

<div class="shot-card">
  <div class="shot-head">
    <span><span class="step-num">2</span> Click Submit &mdash; Instant Mirror Confirmation Popup</span>
    <span class="shot-tag">screenshots/sales_order_msg.png</span>
  </div>
  <img src="{imgs['so_msg']}" alt="Sales Order Submit Message" />
  <div class="shot-caption">
    Submitting <strong>SAL-ORD-2026-00012</strong> shows: <em>"Created draft Purchase Order PUR-ORD-2026-00011 in company ABC Company"</em>.
  </div>
</div>

<div class="shot-card">
  <div class="shot-head">
    <span><span class="step-num">3</span> Open <code>PUR-ORD-2026-00011</code> in ABC Company (Mirrored Draft)</span>
    <span class="shot-tag">screenshots/p-order_mirror_entry_created.png</span>
  </div>
  <img src="{imgs['po_mirror']}" alt="Mirrored Purchase Order" />
  <div class="shot-caption">
    <ul>
      <li><strong>Flipped Automatically:</strong> Company is <code>ABC Company</code>, Supplier is <code>Main Supplier (ABC)</code>, Target Company is <code>MAIN</code>, Item &amp; Rate (<code>Rs 46,000.00</code>) match!</li>
      <li><strong>Orange Safety Banner:</strong> Currency, exchange rates, parties &amp; amounts are strictly locked so ABC cannot accidentally change prices. <strong>Warehouse, Cost Center &amp; Account stay editable</strong> before ABC clicks Submit!</li>
    </ul>
  </div>
</div>

<!-- ==================== LESSON 5 ==================== -->
<div class="page-break"></div>
<div class="lesson-header">
  <div class="lesson-num">LESSON 5</div>
  <div>
    <h2 class="lesson-title">Live Walk-Through #2: Journal Entry &amp; Where <code>TMP-MAIN - AC</code> Lands</h2>
    <p class="lesson-desc">See Debit &amp; Credit flip cleanly from MAIN (<code>ACC-JV-2026-00038</code>) into ABC Company (<code>ACC-JV-2026-00037</code>).</p>
  </div>
</div>

<div class="diagram-box">
  <h3 style="margin-top:0;">Accounting Mirror Side-by-Side (Rs. 100.00)</h3>
  <table>
    <thead>
      <tr>
        <th>Side</th>
        <th>Company</th>
        <th>Row #1 (Party Line)</th>
        <th>Row #2 (Offset / Bridge Line)</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Source JE</strong></td>
        <td><span class="pill pill-main">MAIN</span></td>
        <td><code>Debtors</code> &bull; Party: <code>ABC Customer</code> &bull; <strong>Debit Rs 100</strong></td>
        <td><code>Cash - AM</code> &bull; <strong>Credit Rs 100</strong></td>
      </tr>
      <tr>
        <td><strong>Mirrored JE</strong></td>
        <td><span class="pill pill-abc">ABC Company</span></td>
        <td><code>Creditors</code> &bull; Party: <code>Main Supplier (ABC)</code> &bull; <strong>Credit Rs 100</strong></td>
        <td><span class="pill pill-tmp">TMP-MAIN - AC</span> &bull; <strong>Debit Rs 100</strong></td>
      </tr>
    </tbody>
  </table>
</div>

<div class="shot-card">
  <div class="shot-head">
    <span><span class="step-num">1</span> Source Journal Entry in MAIN (<code>ACC-JV-2026-00038</code>)</span>
    <span class="shot-tag">screenshots/journal_entry.png</span>
  </div>
  <img src="{imgs['je_form']}" alt="Source Journal Entry" />
  <div class="shot-caption">
    Picking Party <code>ABC Customer</code> on Row 1 automatically sets row-level <code>Intercompany Target Company = ABC Company</code>, ticks <code>Is Intercompany</code>, and shows the blue top banner linking to ABC's counterpart.
  </div>
</div>

<div class="two-col">
  <div class="shot-card" style="margin-top:0;">
    <div class="shot-head">
      <span><span class="step-num">2</span> Instant Popup</span>
      <span class="shot-tag">journal_entry_msg.png</span>
    </div>
    <img src="{imgs['je_msg']}" alt="Journal Entry Message" />
    <div class="shot-caption">
      Popup confirms: <em>Created draft Journal Entry ACC-JV-2026-00037 in company ABC Company</em>.
    </div>
  </div>
  <div class="shot-card" style="margin-top:0;">
    <div class="shot-head">
      <span><span class="step-num">3</span> Mirrored JE in ABC Company</span>
      <span class="shot-tag">journal_entry_mirror.png</span>
    </div>
    <img src="{imgs['je_mirror']}" alt="Mirrored Journal Entry" />
    <div class="shot-caption">
      Look at Row 1 &amp; Row 2: <code>Main Supplier (ABC)</code> is <strong>Credited Rs 100.00</strong>, and <span class="pill pill-tmp">TMP-M... (TMP-MAIN - AC)</span> is <strong>Debited Rs 100.00</strong>!
    </div>
  </div>
</div>

<!-- ==================== LESSON 6 ==================== -->
<div class="page-break"></div>
<div class="lesson-header">
  <div class="lesson-num">LESSON 6</div>
  <div>
    <h2 class="lesson-title">Live Walk-Through #3: Payment Entry (<code>Receive</code> &harr; <code>Pay</code>)</h2>
    <p class="lesson-desc">When MAIN records a <strong>Receive</strong> payment, ABC Company automatically gets a matching <strong>Pay</strong> draft.</p>
  </div>
</div>

<div class="shot-card">
  <div class="shot-head">
    <span><span class="step-num">1</span> MAIN Creates Payment Entry: <code>Receive</code> from <code>ABC Customer</code></span>
    <span class="shot-tag">screenshots/payment_entry.png</span>
  </div>
  <img src="{imgs['pe_form']}" alt="Source Payment Entry" />
  <div class="shot-caption">
    Set <code>Payment Type = Receive</code>, <code>Party Type = Customer</code>, and pick <code>ABC Customer</code>. The app immediately enables <strong>Is Intercompany</strong> and targets <strong>ABC Company</strong>.
  </div>
</div>

<div class="two-col">
  <div class="shot-card" style="margin-top:0;">
    <div class="shot-head">
      <span><span class="step-num">2</span> Confirmation Popup</span>
      <span class="shot-tag">payment_entry_msg.png</span>
    </div>
    <img src="{imgs['pe_msg']}" alt="Payment Entry Message" />
    <div class="shot-caption">
      Submitting <code>ACC-PAY-2026-00015</code> triggers: <em>Created draft Payment Entry ACC-PAY-2026-00016 in company ABC Company</em>.
    </div>
  </div>
  <div class="shot-card" style="margin-top:0;">
    <div class="shot-head">
      <span><span class="step-num">3</span> Mirrored Pay Entry in ABC Company</span>
      <span class="shot-tag">payment_entry_mirror_entry.png</span>
    </div>
    <img src="{imgs['pe_mirror']}" alt="Mirrored Payment Entry" />
    <div class="shot-caption">
      <code>ACC-PAY-2026-00016</code> flips automatically to <strong>Payment Type = Pay</strong>, Company = <strong>ABC Company</strong>, Supplier = <strong>Main Supplier (ABC)</strong>, Paid From = <code>TMP-MAIN - AC</code>!
    </div>
  </div>
</div>

<!-- ==================== LESSON 7 ==================== -->
<div class="page-break"></div>
<div class="lesson-header">
  <div class="lesson-num">LESSON 7</div>
  <div>
    <h2 class="lesson-title">5-Rule Cheat Sheet &amp; Screenshots Needed for Volume 2</h2>
    <p class="lesson-desc">Quick memory rules plus the exact screenshots to upload next if you want the complete A-to-Z handbook.</p>
  </div>
</div>

<div class="kid-box green" style="padding:8px 12px;margin:8px 0 10px 0;font-size:9.3pt;">
  <strong class="label">5 Golden Rules to Never Forget</strong>
  1. <strong>My Customer = Your Supplier:</strong> MAIN's <code>ABC Customer</code> always pairs with ABC's <code>Main Supplier (ABC)</code>.<br/>
  2. <strong>One <code>TMP-*</code> Bridge Per Pair:</strong> MAIN uses <code>TMP-ACB-IC - AM</code> for ABC and <code>TMP-JOHN-IC - AM</code> for John so ledgers never mix.<br/>
  3. <strong>Transit Warehouse = Cross-Company Safety Net:</strong> Stock transfers land in the receiver's <code>Goods In Transit</code> warehouse because Company B cannot touch Company A's warehouse.<br/>
  4. <strong>Mirrored Drafts Lock Money, Not Operations:</strong> Prices, currency, and parties are locked; Warehouse, Cost Center, and Account stay editable so the receiving accountant can finish local details.<br/>
  5. <strong>Orphan / Mistake Recovery:</strong> If a linked doc was cancelled or deleted manually, open the <strong>Inter Company</strong> menu &rarr; <em>Delete Mirrored Draft</em> or <em>Unlink Orphan Reference</em> (or remove the row in <em>Inter Company Document Reference</em>).
</div>

<div class="diagram-box" style="padding:10px 12px;margin:8px 0 0 0;">
  <h3 style="margin:0 0 4px 0;font-size:10.5pt;">Screenshots Needed If You Want Volume 2 Added to This Picture Book</h3>
  <p style="margin:0 0 6px 0;font-size:8.8pt;">
    Your 16 screenshots covered Setup, COA, Sales Order &rarr; PO, Journal Entry, and Payment Entry.
    Upload any of these next to weave Chapters 8&ndash;13 into this illustrated workbook:
  </p>
  <table style="font-size:8.4pt;margin:4px 0 0 0;">
    <thead>
      <tr>
        <th style="width:5%;padding:5px 7px;">#</th>
        <th style="width:27%;padding:5px 7px;">Screen / Feature</th>
        <th style="width:38%;padding:5px 7px;">Exact What to Capture</th>
        <th style="width:30%;padding:5px 7px;">Why Readers Need It</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td style="padding:4px 7px;"><strong>1</strong></td>
        <td style="padding:4px 7px;"><strong>Multi-Currency Trade</strong><br/>(MAIN PKR &harr; John USD)</td>
        <td style="padding:4px 7px;">Sales Order / Invoice in <code>MAIN (PKR)</code> &rarr; Mirrored PO/PI in <code>John Company (USD)</code> showing converted rate.</td>
        <td style="padding:4px 7px;">Shows automatic PKR &harr; USD parity using <code>TMP-JOHN-IC - AM</code> &amp; <code>TMP-MAIN - JC</code>.</td>
      </tr>
      <tr>
        <td style="padding:4px 7px;"><strong>2</strong></td>
        <td style="padding:4px 7px;"><strong>Stock Entry Transfer</strong><br/>(Transit Warehouse!)</td>
        <td style="padding:4px 7px;"><code>Stock Entry (Material Issue)</code> in MAIN &rarr; Mirrored <code>Material Receipt</code> landing in <code>Goods In Transit - AC</code> (Same-Currency only).</td>
        <td style="padding:4px 7px;">Visually proves how <code>Transit Warehouse</code> works across companies!</td>
      </tr>
      <tr>
        <td style="padding:4px 7px;"><strong>3</strong></td>
        <td style="padding:4px 7px;"><strong>Sales Invoice &harr; Purchase Invoice</strong></td>
        <td style="padding:4px 7px;">Submitted SI &rarr; Draft PI (and optional Credit Note return sync).</td>
        <td style="padding:4px 7px;">Most used daily billing screen for finance teams.</td>
      </tr>
      <tr>
        <td style="padding:4px 7px;"><strong>4</strong></td>
        <td style="padding:4px 7px;"><strong>Control Console &amp; Wizard</strong></td>
        <td style="padding:4px 7px;"><code>/app/inter-company-console</code> overview cards &amp; Quick Setup Wizard modal.</td>
        <td style="padding:4px 7px;">Shows managers 1-click setup &amp; live KPI dashboard.</td>
      </tr>
      <tr>
        <td style="padding:4px 7px;"><strong>5</strong></td>
        <td style="padding:4px 7px;"><strong>Document Reference &amp; Unlink</strong></td>
        <td style="padding:4px 7px;"><code>Inter Company Document Reference</code> + <em>Inter Company &rarr; Unlink / Delete Mirrored Draft</em> menu.</td>
        <td style="padding:4px 7px;">Teaches staff how to safely unlink or delete drafts.</td>
      </tr>
      <tr>
        <td style="padding:4px 7px;"><strong>6</strong></td>
        <td style="padding:4px 7px;"><strong>Reconciliation / Netting / Elimination</strong></td>
        <td style="padding:4px 7px;"><code>Intercompany Reconciliation</code> report, <code>Netting Cycle</code>, or <code>Elimination Run</code>.</td>
        <td style="padding:4px 7px;">Shows month-end consolidation &amp; zeroing out balances.</td>
      </tr>
      <tr>
        <td style="padding:4px 7px;"><strong>7</strong></td>
        <td style="padding:4px 7px;"><strong>Transfer Pricing &amp; Remote Diagnostics</strong></td>
        <td style="padding:4px 7px;"><code>Transfer Pricing Policy</code> (Cost + Markup %) + <code>Diagnose Network &amp; Firewall</code> modal.</td>
        <td style="padding:4px 7px;">Covers tax markup compliance &amp; multi-server sync.</td>
      </tr>
    </tbody>
  </table>
</div>

</body>
</html>
"""


def render_pdf_with_playwright(html_content: str, output_pdf: Path):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Python 'playwright' package is required for HTML->PDF generation."
        ) from exc

    footer_html = (
        '<div style="width:100%;font-size:8px;color:#64748b;padding:0 14mm;'
        'display:flex;justify-content:space-between;font-family:sans-serif;">'
        "<span>Inter-Company Transactions &mdash; Visual Workbook (Ejaz Tech)</span>"
        '<span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>'
        "</div>"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        try:
            page = browser.new_page()
            page.set_content(html_content, wait_until="networkidle")
            page.pdf(
                path=str(output_pdf),
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template="<div></div>",
                footer_template=footer_html,
                margin={"top": "12mm", "right": "13mm", "bottom": "15mm", "left": "13mm"},
            )
        finally:
            browser.close()


def main():
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    screenshots_dir = repo_root / "screenshots"
    if not screenshots_dir.exists():
        screenshots_dir = script_dir / "screenshots"

    logo_svg = script_dir / "public" / "images" / "inter_company_logo.svg"
    if not logo_svg.exists():
        logo_svg = None

    public_pdf = script_dir / "public" / "Inter_Company_Transactions_Visual_Workbook.pdf"
    root_pdf = repo_root / "Inter_Company_Transactions_Visual_Workbook.pdf"
    public_pdf.parent.mkdir(parents=True, exist_ok=True)

    html = build_html(screenshots_dir, logo_svg_path=logo_svg)
    render_pdf_with_playwright(html, public_pdf)
    shutil.copyfile(public_pdf, root_pdf)

    size_kb = public_pdf.stat().st_size / 1024
    print(f"Generated {public_pdf} ({size_kb:.1f} KB)")
    print(f"Copied to {root_pdf}")


if __name__ == "__main__":
    main()
