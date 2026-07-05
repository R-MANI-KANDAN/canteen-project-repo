# Description: Utility functions for QR code generation, invoice numbering, and PDF receipts.
import os
import uuid
import qrcode
import logging
from io import BytesIO
from datetime import datetime
from decimal import Decimal

from django.conf import settings

logger = logging.getLogger(__name__)


def generate_invoice_number():
    """
    Generates a unique invoice number in format: LICET-YYYYMMDD-NNNN.

    Uses a simple counter approach: counts existing invoices for today + 1.
    """
    from .models import Payment

    today = datetime.now().strftime('%Y%m%d')
    prefix = f"LICET-{today}-"

    # Count existing invoices for today
    today_count = Payment.objects.filter(
        remarks__contains=prefix
    ).count()

    invoice_number = f"{prefix}{today_count + 1:04d}"
    return invoice_number


def generate_qr_code(order_ref, student_id, amount, invoice_number):
    """
    Generates a QR code image and saves it to the media directory.

    The QR code contains:
    - Order reference
    - Student ID
    - Amount paid
    - Invoice number
    - Timestamp

    Args:
        order_ref: Order reference string (e.g., LCT-0001)
        student_id: Student ID / username
        amount: Payment amount as string
        invoice_number: Generated invoice number

    Returns:
        str: Relative path to the saved QR code image
    """
    qr_data = (
        f"LICET Cafeteria\n"
        f"Order: {order_ref}\n"
        f"Student: {student_id}\n"
        f"Amount: Rs.{amount}\n"
        f"Invoice: {invoice_number}\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color='#1a1a2e', back_color='#ffffff')

    # Ensure directory exists
    qr_dir = os.path.join(settings.MEDIA_ROOT, 'qr_codes')
    os.makedirs(qr_dir, exist_ok=True)

    # Save with unique filename
    filename = f"qr_{order_ref}_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(qr_dir, filename)
    img.save(filepath)

    relative_path = f"qr_codes/{filename}"
    logger.info(f"QR code generated: {relative_path}")
    return relative_path


def generate_receipt_pdf(payment, cart_items, order_ref, invoice_number, pickup_slot):
    """
    Generates a professional PDF receipt using ReportLab.

    Args:
        payment: Payment model instance
        cart_items: List of dicts with name, qty, price, subtotal
        order_ref: Order reference string
        invoice_number: Invoice number
        pickup_slot: Pickup slot string

    Returns:
        BytesIO: PDF file as bytes buffer ready for download
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm
    )

    styles = getSampleStyleSheet()
    elements = []

    # Custom styles
    title_style = ParagraphStyle(
        'ReceiptTitle', parent=styles['Title'],
        fontSize=22, textColor=HexColor('#1a1a2e'),
        spaceAfter=2 * mm
    )
    subtitle_style = ParagraphStyle(
        'ReceiptSubtitle', parent=styles['Normal'],
        fontSize=10, textColor=HexColor('#666666'),
        alignment=TA_CENTER, spaceAfter=8 * mm
    )
    heading_style = ParagraphStyle(
        'SectionHeading', parent=styles['Heading2'],
        fontSize=12, textColor=HexColor('#ff6b35'),
        spaceBefore=6 * mm, spaceAfter=3 * mm
    )
    normal_style = ParagraphStyle(
        'ReceiptNormal', parent=styles['Normal'],
        fontSize=10, leading=14
    )
    right_style = ParagraphStyle(
        'RightAligned', parent=styles['Normal'],
        fontSize=10, alignment=TA_RIGHT
    )
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=9, textColor=HexColor('#999999'),
        alignment=TA_CENTER, spaceBefore=10 * mm
    )

    # ── Header ──
    elements.append(Paragraph("LICET Cafeteria", title_style))
    elements.append(Paragraph(
        "Loyola-ICAM College of Engineering and Technology | Chennai",
        subtitle_style
    ))

    # ── Invoice Details ──
    elements.append(Paragraph("Invoice Details", heading_style))

    info_data = [
        ['Invoice Number:', invoice_number],
        ['Date:', datetime.now().strftime('%d %B %Y, %I:%M %p')],
        ['Order Reference:', order_ref],
        ['Student:', payment.user.get_full_name() or payment.user.username],
        ['Payment ID:', payment.razorpay_payment_id or '—'],
        ['Payment Method:', payment.get_payment_method_display()],
        ['Status:', 'Paid ✓'],
    ]

    info_table = Table(info_data, colWidths=[45 * mm, 120 * mm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#333333')),
        ('TEXTCOLOR', (1, 0), (1, -1), HexColor('#555555')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 5 * mm))

    # ── Items Table ──
    elements.append(Paragraph("Order Items", heading_style))

    items_header = ['Item', 'Qty', 'Unit Price', 'Subtotal']
    items_data = [items_header]
    for item in cart_items:
        items_data.append([
            item['name'],
            str(item['qty']),
            f"Rs.{item['price']}",
            f"Rs.{item['subtotal']}",
        ])

    # Total row
    items_data.append(['', '', 'Total:', f"Rs.{payment.amount}"])

    items_table = Table(
        items_data,
        colWidths=[80 * mm, 20 * mm, 30 * mm, 35 * mm]
    )
    items_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#ff6b35')),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
        # Body rows
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        # Grid
        ('LINEBELOW', (0, 0), (-1, 0), 1, HexColor('#ff6b35')),
        ('LINEBELOW', (0, -2), (-1, -2), 0.5, HexColor('#cccccc')),
        # Total row
        ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (-2, -1), (-1, -1), 11),
        ('LINEABOVE', (-2, -1), (-1, -1), 1, HexColor('#333333')),
        # Alternating row colors
        *[('BACKGROUND', (0, i), (-1, i), HexColor('#f9f9f9'))
          for i in range(2, len(items_data) - 1, 2)],
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 5 * mm))

    # ── Pickup Info ──
    elements.append(Paragraph("Pickup Information", heading_style))
    pickup_data = [
        ['Pickup Slot:', pickup_slot or '—'],
    ]
    pickup_table = Table(pickup_data, colWidths=[45 * mm, 120 * mm])
    pickup_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(pickup_table)
    elements.append(Spacer(1, 5 * mm))

    # ── QR Code ──
    qr_path = None
    if payment.remarks and 'QR: ' in payment.remarks:
        qr_relative = payment.remarks.split('QR: ')[-1].strip()
        qr_full_path = os.path.join(settings.MEDIA_ROOT, qr_relative)
        if os.path.exists(qr_full_path):
            qr_path = qr_full_path

    if qr_path:
        elements.append(Paragraph("Pickup QR Code", heading_style))
        qr_img = Image(qr_path, width=40 * mm, height=40 * mm)
        elements.append(qr_img)
        elements.append(Spacer(1, 3 * mm))

    # ── Footer ──
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        "Thank you for ordering from LICET Cafeteria!",
        footer_style
    ))
    elements.append(Paragraph(
        "This is a computer-generated receipt and does not require a signature.",
        footer_style
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer
