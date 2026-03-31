from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file
from flask_login import login_required, current_user
from app.extensions import db
from app.models import GFSReconciliation
import csv
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from werkzeug.utils import secure_filename

bp = Blueprint('gfs', __name__, url_prefix='/gfs')

# Account codes
ACCOUNT_FOOD_SA = "23.1.351.5610.200"  # School Age - Food
ACCOUNT_GRANT_GSRP = "23.1.118.5110.000.3436.00629.0"  # GSRP - Grant
# Allocation percentages
SA_PERCENT = 0.67
GSRP_PERCENT = 0.33

# Email config constants
EMAIL_FROM_NAME = "Hari (Adam's AI Assistant)"
EMAIL_FROM_ADDRESS = "behindthegarage.dev@gmail.com"
EMAIL_REPLY_TO = "adam.brussow@okemosk12.net"

EMAIL_SIGNATURE = """--
Hari 🌿
AI Assistant for Adam Brussow
Club Kinawa Director

This message was sent by Hari, Adam's AI assistant.
For direct contact: adam.brussow@okemosk12.net
"""


def item_includes_gsrp(item):
    """Return whether an item should use the standard GSRP split.

    Supports both the current `include_in_gsrp` flag and legacy `is_disposable`
    records so existing pending reconciliations do not silently change meaning.
    """
    if 'include_in_gsrp' in item:
        return bool(item.get('include_in_gsrp'))

    if 'is_disposable' in item:
        return not bool(item.get('is_disposable'))

    return False


def classify_item(include_in_gsrp=False):
    """Classify item based on whether it should use the GSRP split."""
    if include_in_gsrp:
        return {
            'type': 'gsrp_split',
            'sa_amount': SA_PERCENT,
            'gsrp_amount': GSRP_PERCENT,
            'sa_account': ACCOUNT_FOOD_SA,
            'gsrp_account': ACCOUNT_GRANT_GSRP,
            'notes': f'Used by GSRP - {SA_PERCENT*100:.0f}% SA / {GSRP_PERCENT*100:.0f}% GSRP'
        }

    return {
        'type': 'school_age_only',
        'sa_amount': 1.0,
        'gsrp_amount': 0.0,
        'sa_account': ACCOUNT_FOOD_SA,
        'gsrp_account': None,
        'notes': 'School Age only - 100% School Age'
    }


def parse_gfs_csv(csv_path):
    """Parse GFS CSV export.

    New reconciliations default items to School Age only until explicitly marked
    for GSRP use during review.
    """
    items = []
    total = 0.0
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            desc = row.get('Item Description', '') or ''
            if not desc:
                continue
            
            desc = desc.strip()
            
            # Skip section headers
            if desc and any(section in desc.lower() for section in ['cooler', 'freezer', 'grocery', 'dry']):
                continue
            
            price_str = row.get('Price (Case/Unit)', '0').replace(',', '').replace('$', '')
            qty_str = row.get('Quantity Shipped', '1').strip()
            item_num = row.get('Item Number', '').strip()
            
            try:
                price = float(price_str) if price_str else 0.0
                qty = int(float(qty_str)) if qty_str else 1
            except ValueError:
                price = 0.0
                qty = 1
            
            if desc and price > 0:
                extended = price * qty
                classification = classify_item(include_in_gsrp=False)
                
                items.append({
                    'item_number': item_num,
                    'description': desc,
                    'qty': qty,
                    'unit_price': price,
                    'extended': extended,
                    'include_in_gsrp': False,
                    'classification': classification,
                    'sa_allocation': extended * classification['sa_amount'],
                    'gsrp_allocation': extended * classification['gsrp_amount']
                })
                total += extended
    
    return items, total


def extract_invoice_info_from_pdf(pdf_path):
    """Extract invoice number and date from GFS PDF."""
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', pdf_path, '-'],
            capture_output=True, text=True
        )
        text = result.stdout
        lines = text.split('\n')
        
        invoice_num = None
        date_str = None
        
        # Method 1: Look for "Invoice" followed by number on same line
        for line in lines:
            match = re.search(r'Invoice\s+(\d{9,10})', line)
            if match:
                invoice_num = match.group(1)
                break
        
        # Method 2: Look for "Invoice Date" followed by date
        for line in lines:
            match = re.search(r'Invoice Date\s+(\d{2}/\d{2}/\d{4})', line)
            if match:
                date_str = match.group(1)
                break
        
        # Method 3: Fallback - standalone 9-10 digit number
        if not invoice_num:
            for i, line in enumerate(lines):
                match = re.search(r'\b(\d{9,10})\b', line)
                if match:
                    context = ' '.join(lines[max(0,i-2):min(len(lines),i+3)])
                    if 'Purchase Order' not in context:
                        invoice_num = match.group(1)
                        break
        
        return invoice_num, date_str
    except:
        return None, None


def parse_date_from_filename(filename):
    """Extract date from filename (MMDDYYYY)."""
    match = re.search(r'(\d{8})', filename)
    if match:
        date_code = match.group(1)
        return f"{date_code[0:2]}/{date_code[2:4]}/{date_code[4:8]}"
    return None


def recalculate_allocations(items):
    """Recalculate allocations based on GSRP-use flags."""
    for item in items:
        include_in_gsrp = item_includes_gsrp(item)
        item['include_in_gsrp'] = include_in_gsrp
        classification = classify_item(include_in_gsrp=include_in_gsrp)
        item['classification'] = classification
        item['sa_allocation'] = item['extended'] * classification['sa_amount']
        item['gsrp_allocation'] = item['extended'] * classification['gsrp_amount']
    return items


def generate_reconciliation_html(items, total, invoice_num, date_str, csv_filename, rec_id):
    """Generate professional HTML reconciliation."""
    
    if not date_str:
        date_str = datetime.now().strftime("%m/%d/%Y")
    
    invoice_display = f"#{invoice_num}" if invoice_num else "(Pending)"
    
    # Calculate totals
    sa_total = sum(item['sa_allocation'] for item in items)
    gsrp_total = sum(item['gsrp_allocation'] for item in items)
    
    gsrp_item_count = sum(1 for item in items if item_includes_gsrp(item))
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>GFS Invoice Reconciliation</title>
    <style>
        @page {{ margin: 0.75in; size: letter; }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
            font-size: 10pt; line-height: 1.4; color: #333; margin: 0; padding: 0;
        }}
        .header {{
            border-bottom: 3px solid #1a5276; padding-bottom: 15px; margin-bottom: 25px;
        }}
        .school-name {{
            font-size: 16pt; font-weight: 600; color: #1a5276; letter-spacing: 0.5px;
        }}
        .department {{
            font-size: 11pt; color: #666; margin-top: 3px;
        }}
        .doc-title {{
            font-size: 14pt; font-weight: 600; color: #1a5276;
            margin: 25px 0 15px 0; text-transform: uppercase; letter-spacing: 1px;
        }}
        .info-grid {{ display: table; width: 100%; margin-bottom: 20px; }}
        .info-row {{ display: table-row; }}
        .info-label {{
            display: table-cell; width: 140px; font-weight: 600; color: #555; padding: 4px 0;
        }}
        .info-value {{ display: table-cell; padding: 4px 0; }}
        .vendor-info {{
            background: #f8f9fa; border-left: 4px solid #1a5276;
            padding: 12px 15px; margin: 20px 0;
        }}
        .vendor-name {{ font-weight: 600; font-size: 11pt; color: #1a5276; }}
        table {{
            width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 9pt;
        }}
        thead {{ display: table-header-group; }}
        th {{
            background-color: #1a5276; color: white; font-weight: 600;
            text-align: left; padding: 10px 8px; border: none;
        }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; vertical-align: top; }}
        tr:nth-child(even) {{ background-color: #f8f9fa; }}
        .numeric {{ text-align: right; font-family: "Courier New", monospace; }}
        .total-row {{
            font-weight: 600; background-color: #e8f4f8 !important;
            border-top: 2px solid #1a5276;
        }}
        .total-row td {{ border-bottom: none; padding-top: 10px; padding-bottom: 10px; }}
        .allocation-section {{ margin-top: 30px; page-break-inside: avoid; }}
        .section-title {{
            font-size: 12pt; font-weight: 600; color: #1a5276;
            border-bottom: 2px solid #1a5276; padding-bottom: 5px; margin-bottom: 15px;
        }}
        .allocation-table {{ width: 100%; border: 1px solid #ddd; }}
        .allocation-table th {{
            background-color: #5dade2; font-size: 9pt; padding: 8px;
        }}
        .allocation-table td {{ padding: 10px 8px; border: 1px solid #ddd; }}
        .account-code {{
            font-family: "Courier New", monospace; font-size: 9.5pt;
            background: #f0f0f0; padding: 2px 6px; border-radius: 3px;
        }}
        .signature-section {{ margin-top: 50px; page-break-inside: avoid; }}
        .signature-line {{
            border-top: 1px solid #333; width: 250px; margin-top: 30px;
            padding-top: 5px; font-size: 9pt; color: #666;
        }}
        .footer {{
            margin-top: 40px; padding-top: 15px; border-top: 1px solid #ddd;
            font-size: 8pt; color: #888; text-align: center;
        }}
        .disposable-badge {{
            background: #fef3c7; color: #92400e; font-size: 7pt;
            padding: 1px 4px; border-radius: 2px; margin-left: 4px;
            white-space: nowrap; display: inline-block;
        }}
        .notes {{
            margin-top: 25px; padding: 15px; background: #fff8e1;
            border-left: 4px solid #f39c12; font-size: 9pt;
        }}
        .notes-title {{ font-weight: 600; color: #d68910; margin-bottom: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="school-name">Okemos Public Schools</div>
        <div class="department">Kids Club – Kinawa Middle School</div>
    </div>
    
    <div class="doc-title">Invoice Reconciliation</div>
    
    <div class="info-grid">
        <div class="info-row">
            <div class="info-label">Invoice Number:</div>
            <div class="info-value">{invoice_display}</div>
        </div>
        <div class="info-row">
            <div class="info-label">Invoice Date:</div>
            <div class="info-value">{date_str}</div>
        </div>
        <div class="info-row">
            <div class="info-label">Reconciliation Date:</div>
            <div class="info-value">{datetime.now().strftime("%m/%d/%Y")}</div>
        </div>
        <div class="info-row">
            <div class="info-label">Total Amount:</div>
            <div class="info-value" style="font-weight: 600; font-size: 11pt;">${total:,.2f}</div>
        </div>
    </div>
    
    <div class="vendor-info">
        <div class="vendor-name">Gordon Food Service</div>
        <div>Snacks and Food Supplies</div>
    </div>
    
    <table>
        <thead>
            <tr>
                <th style="width: 6%;">Qty</th>
                <th style="width: 48%;">Description</th>
                <th style="width: 14%;">Extended</th>
                <th style="width: 14%;">SA</th>
                <th style="width: 14%;">GSRP</th>
            </tr>
        </thead>
        <tbody>
"""

    for item in items:
        desc_display = item['description']
        html += f"""            <tr>
                <td>{item['qty']}</td>
                <td>{desc_display}</td>
                <td class="numeric">${item['extended']:,.2f}</td>
                <td class="numeric">${item['sa_allocation']:,.2f}</td>
                <td class="numeric">${item['gsrp_allocation']:,.2f}</td>
            </tr>
"""

    html += f"""            <tr class="total-row">
                <td colspan="2" style="text-align: right;">Total</td>
                <td class="numeric">${total:,.2f}</td>
                <td class="numeric">${sa_total:,.2f}</td>
                <td class="numeric">${gsrp_total:,.2f}</td>
            </tr>
        </tbody>
    </table>
    
    <div class="allocation-section">
        <div class="section-title">Budget Allocation</div>
        <table class="allocation-table">
            <thead>
                <tr>
                    <th>Account</th>
                    <th>Account Code</th>
                    <th>Amount</th>
                    <th>Percentage</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>School Age - Food</strong></td>
                    <td><span class="account-code">{ACCOUNT_FOOD_SA}</span></td>
                    <td class="numeric">${sa_total:,.2f}</td>
                    <td class="numeric">{sa_total/total*100 if total > 0 else 0:.1f}%</td>
                </tr>
                <tr>
                    <td><strong>GSRP - Grant</strong></td>
                    <td><span class="account-code">{ACCOUNT_GRANT_GSRP}</span></td>
                    <td class="numeric">${gsrp_total:,.2f}</td>
                    <td class="numeric">{gsrp_total/total*100 if total > 0 else 0:.1f}%</td>
                </tr>
                <tr style="font-weight: 600; background-color: #e8f4f8;">
                    <td colspan="2" style="text-align: right;">Total Allocated:</td>
                    <td class="numeric">${total:,.2f}</td>
                    <td class="numeric">100%</td>
                </tr>
            </tbody>
        </table>
    </div>
    
    <div class="notes">
        <div class="notes-title">Allocation Notes:</div>
        <div>• Items checked for GSRP use: 67% School Age / 33% GSRP ({gsrp_item_count} items marked)</div>
        <div>• Items not checked for GSRP use: 100% School Age</div>
        <div>• Original GFS invoice attached for reference</div>
    </div>
    
    <div class="signature-section">
        <div class="signature-line">Program Director Signature & Date</div>
    </div>
    
    <div class="footer">
        Okemos Public Schools · Kids Club · Kinawa Middle School<br>
        Invoice Reconciliation Document
    </div>
</body>
</html>
"""

    return html


def html_to_pdf(html_content, output_path):
    """Convert HTML to PDF using wkhtmltopdf."""
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = f.name

        wkhtmltopdf_path = (
            shutil.which('wkhtmltopdf')
            or next(
                (
                    candidate for candidate in (
                        '/usr/bin/wkhtmltopdf',
                        '/usr/local/bin/wkhtmltopdf',
                    ) if os.path.exists(candidate)
                ),
                None,
            )
        )

        if not wkhtmltopdf_path:
            current_app.logger.warning("wkhtmltopdf not found")
            os.unlink(html_file)
            return False

        result = subprocess.run(
            [wkhtmltopdf_path,
             '--enable-local-file-access',
             '--page-size', 'Letter',
             '--margin-top', '0.75in',
             '--margin-bottom', '0.75in',
             '--margin-left', '0.75in',
             '--margin-right', '0.75in',
             '--print-media-type',
             html_file, output_path],
            capture_output=True, text=True
        )
        os.unlink(html_file)

        if result.returncode == 0 and os.path.exists(output_path):
            return True

        current_app.logger.error(
            "wkhtmltopdf failed with code %s: %s",
            result.returncode,
            (result.stderr or '').strip()
        )
    except FileNotFoundError:
        current_app.logger.warning("wkhtmltopdf not found")
    return False


def load_smtp_config():
    """Load SMTP config from file or environment."""
    config_paths = [
        '/home/openclaw/gfs_smtp.conf',
        os.path.expanduser('~/.openclaw/workspace/gfs_smtp.conf'),
        'gfs_smtp.conf'
    ]
    
    config = {}
    for path in config_paths:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
            break
    
    # Fallback to environment variables
    config.setdefault('SMTP_HOST', os.getenv('SMTP_HOST', 'smtp.gmail.com'))
    config.setdefault('SMTP_PORT', os.getenv('SMTP_PORT', '587'))
    config.setdefault('SMTP_USER', os.getenv('SMTP_USER', 'behindthegarage.dev@gmail.com'))
    config.setdefault('SMTP_PASSWORD', os.getenv('SMTP_PASSWORD', ''))
    config.setdefault('FROM_EMAIL', os.getenv('FROM_EMAIL', 'behindthegarage.dev@gmail.com'))
    config.setdefault('TO_EMAIL', os.getenv('TO_EMAIL', 'adam.brussow@okemosk12.net'))
    
    return config


def send_email_smtp(subject, body, attachments=None, to_email=None):
    """Send email via SMTP with optional attachments."""
    import smtplib
    import ssl
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders
    
    config = load_smtp_config()
    
    if not config.get('SMTP_PASSWORD'):
        current_app.logger.warning("SMTP password not configured")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_FROM_NAME} <{EMAIL_FROM_ADDRESS}>"
        msg['To'] = to_email or config['TO_EMAIL']
        msg['Reply-To'] = EMAIL_REPLY_TO
        msg['Subject'] = subject
        
        full_body = body + EMAIL_SIGNATURE
        msg.attach(MIMEText(full_body, "plain"))
        
        if attachments:
            for filepath in attachments:
                if os.path.exists(filepath):
                    filename = os.path.basename(filepath)
                    with open(filepath, 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                    msg.attach(part)
        
        context = ssl.create_default_context()
        with smtplib.SMTP(config['SMTP_HOST'], int(config['SMTP_PORT'])) as server:
            server.starttls(context=context)
            server.login(config['SMTP_USER'], config['SMTP_PASSWORD'])
            server.send_message(msg)
        
        return True
    except Exception as e:
        current_app.logger.error(f"Email failed: {e}")
        return False


def get_upload_path():
    """Get path for GFS uploads."""
    upload_dir = os.path.join(current_app.instance_path, 'gfs_uploads')
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def get_original_invoice_path(rec):
    """Return the uploaded source invoice PDF path for a reconciliation."""
    reconciled_data = rec.reconciled_data or {}
    source_pdf_path = reconciled_data.get('source_pdf_path')
    if source_pdf_path and os.path.exists(source_pdf_path):
        return source_pdf_path

    # Legacy fallback: pending records originally stored the uploaded invoice PDF
    # in `pdf_path` before approval generated the final reconciliation PDF.
    if rec.status == 'pending' and rec.pdf_path and os.path.exists(rec.pdf_path):
        return rec.pdf_path

    return None


@bp.route('/')
@login_required
def index():
    """GFS reconciliation dashboard - upload interface."""
    # Get recent reconciliations
    recent = GFSReconciliation.query.order_by(GFSReconciliation.created_at.desc()).limit(10).all()
    return render_template('gfs/index.html', title='GFS Reconciliation', recent=recent)


@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    """Handle CSV and PDF upload."""
    csv_file = request.files.get('csv_file')
    pdf_file = request.files.get('pdf_file')
    
    if not csv_file or not csv_file.filename:
        flash('Please upload a CSV file', 'error')
        return redirect(url_for('gfs.index'))
    
    upload_dir = get_upload_path()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save CSV
    csv_filename = secure_filename(f"{timestamp}_{csv_file.filename}")
    csv_path = os.path.join(upload_dir, csv_filename)
    csv_file.save(csv_path)
    
    # Save PDF if provided
    pdf_path = None
    pdf_filename = None
    if pdf_file and pdf_file.filename:
        pdf_filename = secure_filename(f"{timestamp}_{pdf_file.filename}")
        pdf_path = os.path.join(upload_dir, pdf_filename)
        pdf_file.save(pdf_path)
    
    # Extract invoice info from PDF if available
    invoice_num = None
    date_str = None
    if pdf_path and os.path.exists(pdf_path):
        invoice_num, pdf_date = extract_invoice_info_from_pdf(pdf_path)
        if pdf_date:
            date_str = pdf_date
    
    # Try filename as fallback
    if not date_str:
        date_str = parse_date_from_filename(csv_file.filename)
    
    # Parse CSV
    try:
        items, total = parse_gfs_csv(csv_path)
    except Exception as e:
        flash(f'Error parsing CSV: {str(e)}', 'error')
        return redirect(url_for('gfs.index'))
    
    if not items:
        flash('No valid items found in CSV', 'error')
        return redirect(url_for('gfs.index'))
    
    # Parse date for database
    invoice_date = None
    if date_str:
        try:
            invoice_date = datetime.strptime(date_str, '%m/%d/%Y').date()
        except ValueError:
            pass
    
    # Create reconciliation record
    rec = GFSReconciliation(
        invoice_number=invoice_num or f"PENDING_{timestamp}",
        invoice_date=invoice_date,
        total_amount=total,
        status='pending',
        csv_path=csv_path,
        pdf_path=pdf_path,
        reconciled_data={
            'items': items,
            'csv_filename': csv_file.filename,
            'pdf_filename': pdf_file.filename if pdf_file else None,
            'source_pdf_path': pdf_path,
            'date_str': date_str
        }
    )
    db.session.add(rec)
    db.session.commit()
    
    flash(f'Upload successful! {len(items)} items ready for review.', 'success')
    return redirect(url_for('gfs.review', rec_id=rec.id))


@bp.route('/review/<int:rec_id>')
@login_required
def review(rec_id):
    """Review and edit reconciliation."""
    rec = GFSReconciliation.query.get_or_404(rec_id)
    
    items = rec.reconciled_data.get('items', [])

    needs_save = any('include_in_gsrp' not in item for item in items)
    items = recalculate_allocations(items)
    if needs_save:
        rec.reconciled_data['items'] = items
        db.session.commit()

    total = float(rec.total_amount) if rec.total_amount else 0
    
    # Calculate totals
    sa_total = sum(item.get('sa_allocation', 0) for item in items)
    gsrp_total = sum(item.get('gsrp_allocation', 0) for item in items)
    gsrp_item_count = sum(1 for item in items if item.get('include_in_gsrp', False))
    original_invoice_available = bool(get_original_invoice_path(rec))
    
    return render_template('gfs/review.html', 
        title='Review GFS Reconciliation',
        rec=rec,
        items=items,
        total=total,
        sa_total=sa_total,
        gsrp_total=gsrp_total,
        gsrp_item_count=gsrp_item_count,
        original_invoice_available=original_invoice_available,
        sa_account=ACCOUNT_FOOD_SA,
        gsrp_account=ACCOUNT_GRANT_GSRP
    )


@bp.route('/review/<int:rec_id>/details', methods=['POST'])
@login_required
def update_details(rec_id):
    """Update invoice details for a pending reconciliation."""
    rec = GFSReconciliation.query.get_or_404(rec_id)

    if rec.status != 'pending':
        flash('Cannot modify approved reconciliation', 'error')
        return redirect(url_for('gfs.review', rec_id=rec_id))

    invoice_number = (request.form.get('invoice_number') or '').strip()
    if not invoice_number:
        flash('Invoice number is required', 'error')
        return redirect(url_for('gfs.review', rec_id=rec_id))

    rec.invoice_number = invoice_number
    db.session.commit()
    flash('Invoice details updated', 'success')
    return redirect(url_for('gfs.review', rec_id=rec_id))


@bp.route('/review/<int:rec_id>/recalculate', methods=['POST'])
@login_required
def recalculate_review(rec_id):
    """Update GSRP item selections and recalculate allocations."""
    rec = GFSReconciliation.query.get_or_404(rec_id)
    
    if rec.status != 'pending':
        flash('Cannot modify approved reconciliation', 'error')
        return redirect(url_for('gfs.review', rec_id=rec_id))
    
    items = rec.reconciled_data.get('items', [])
    selected_indexes = set(request.form.getlist('include_in_gsrp'))

    for index, item in enumerate(items):
        item['include_in_gsrp'] = str(index) in selected_indexes

    items = recalculate_allocations(items)
    rec.reconciled_data['items'] = items

    total = sum(item['extended'] for item in items)
    rec.total_amount = total

    db.session.commit()
    flash('Reconciliation updated', 'success')
    
    return redirect(url_for('gfs.review', rec_id=rec_id))


@bp.route('/review/<int:rec_id>/approve', methods=['POST'])
@login_required
def approve(rec_id):
    """Approve reconciliation and generate PDF."""
    rec = GFSReconciliation.query.get_or_404(rec_id)
    
    if rec.status != 'pending':
        flash('Reconciliation already processed', 'error')
        return redirect(url_for('gfs.review', rec_id=rec_id))
    
    items = rec.reconciled_data.get('items', [])
    total = sum(item['extended'] for item in items)
    date_str = rec.reconciled_data.get('date_str')
    csv_filename = rec.reconciled_data.get('csv_filename', 'unknown.csv')

    invoice_number = (request.form.get('invoice_number') or rec.invoice_number or '').strip()
    if not invoice_number:
        flash('Invoice number is required before approval', 'error')
        return redirect(url_for('gfs.review', rec_id=rec_id))
    rec.invoice_number = invoice_number

    if rec.reconciled_data is None:
        rec.reconciled_data = {}
    if not rec.reconciled_data.get('source_pdf_path'):
        rec.reconciled_data['source_pdf_path'] = get_original_invoice_path(rec)
    
    # Generate PDF
    html = generate_reconciliation_html(items, total, rec.invoice_number, date_str, csv_filename, rec.id)
    
    upload_dir = get_upload_path()
    pdf_filename = f"GFS_Reconciliation_{rec.invoice_number}_{datetime.now().strftime('%Y%m%d')}.pdf"
    pdf_path = os.path.join(upload_dir, pdf_filename)
    
    if html_to_pdf(html, pdf_path):
        # Update record
        rec.pdf_path = pdf_path
        rec.status = 'approved'
        rec.approved_at = datetime.utcnow()
        rec.approved_by = current_user.username
        db.session.commit()
        
        # Send email
        email_to = request.form.get('email_to') or 'adam.brussow@okemosk12.net'
        attachments = [pdf_path]
        if rec.csv_path and os.path.exists(rec.csv_path):
            attachments.append(rec.csv_path)
        
        subject = f'GFS Reconciliation Approved - {rec.invoice_number}'
        body = f"""The GFS invoice reconciliation has been approved.

Invoice: {rec.invoice_number}
Date: {date_str or 'N/A'}
Total: ${total:,.2f}

Approved by: {current_user.username}
Approved at: {rec.approved_at.strftime('%m/%d/%Y %H:%M')}

Please find the reconciliation report attached.
"""
        
        if send_email_smtp(subject, body, attachments=attachments, to_email=email_to):
            flash(f'Reconciliation approved and emailed to {email_to}', 'success')
        else:
            flash('Reconciliation approved but email failed (check SMTP config)', 'warning')
    else:
        flash('PDF generation failed. Make sure wkhtmltopdf is installed.', 'error')
    
    return redirect(url_for('gfs.history'))


@bp.route('/review/<int:rec_id>/reject', methods=['POST'])
@login_required
def reject(rec_id):
    """Reject reconciliation."""
    rec = GFSReconciliation.query.get_or_404(rec_id)
    
    if rec.status != 'pending':
        flash('Reconciliation already processed', 'error')
        return redirect(url_for('gfs.review', rec_id=rec_id))
    
    rec.status = 'rejected'
    rec.updated_at = datetime.utcnow()
    db.session.commit()
    
    flash('Reconciliation rejected', 'success')
    return redirect(url_for('gfs.history'))


@bp.route('/history')
@login_required
def history():
    """View all reconciliations."""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    
    query = GFSReconciliation.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    reconciliations = query.order_by(GFSReconciliation.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('gfs/history.html', 
        title='GFS Reconciliation History',
        reconciliations=reconciliations,
        status_filter=status_filter
    )


@bp.route('/download/<int:rec_id>')
@login_required
def download_pdf(rec_id):
    """Download reconciliation PDF."""
    rec = GFSReconciliation.query.get_or_404(rec_id)
    
    if not rec.pdf_path or not os.path.exists(rec.pdf_path):
        flash('PDF not available', 'error')
        return redirect(url_for('gfs.review', rec_id=rec_id))
    
    return send_file(rec.pdf_path, as_attachment=True)


@bp.route('/source-invoice/<int:rec_id>')
@login_required
def preview_source_invoice(rec_id):
    """Preview the original uploaded invoice PDF inline."""
    rec = GFSReconciliation.query.get_or_404(rec_id)
    source_pdf_path = get_original_invoice_path(rec)

    if not source_pdf_path:
        flash('Original invoice PDF not available', 'error')
        return redirect(url_for('gfs.review', rec_id=rec_id))

    return send_file(source_pdf_path, mimetype='application/pdf', as_attachment=False)
