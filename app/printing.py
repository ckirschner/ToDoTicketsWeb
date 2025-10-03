# app/printing.py
from __future__ import annotations
import os
import textwrap
import logging
from pathlib import Path
from typing import Optional

from .storage import archive_paths
from pathlib import Path
from datetime import datetime
from typing import Optional

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available, environment variables must be set externally

# Configure logging for printing operations
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PRINT_BACKEND = os.getenv("PRINT_BACKEND", "file").lower()
logger.info(f"PRINT: Backend configuration: {PRINT_BACKEND}")

class PrintResult:
    def __init__(self, backend: str, pdf_path: Optional[Path] = None, job_id: Optional[str] = None):
        self.backend = backend
        self.pdf_path = pdf_path
        self.job_id = job_id

# ---------- ESC/POS helpers (only imported when needed) ----------

def _escpos_connect():
    """
    Connect to an ESC/POS printer - using your proven File method
    """
    device = os.getenv("ESCPOS_DEVICE", "/dev/usb/lp0")
    logger.info(f"ESCPOS: Connecting to device: {device}")
    
    try:
        from escpos.printer import File
        printer = File(device)
        logger.info(f"ESCPOS: Successfully connected to {device}")
        return printer
    except ImportError as e:
        logger.error(f"ESCPOS: Failed to import escpos library: {e}")
        raise
    except Exception as e:
        logger.error(f"ESCPOS: Failed to connect to device {device}: {e}")
        raise

# ---------------------
# EXACT APPROVED ADHD TICKET IMPLEMENTATION
# ---------------------

# Config from patch brief
PAPER_DOTS = 576  # 80mm @ 203dpi
MARGIN_X = 6      # Minimal edge margins
TITLE_PT = 48     # Much bigger for visibility from afar
LABEL_PT = 16
BODY_PT = 22
SMALL_PT = 18

def _load_font(size):
    """Load DejaVu Sans with fallbacks - exact from approved format"""
    from PIL import ImageFont
    for path in [
        "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

def _text_box(draw, s, font):
    """3.7-safe bbox: returns (l,t,r,b) - exact from approved format"""
    if hasattr(draw, "textbbox"):
        return draw.textbbox((0,0), s, font=font)
    w, h = draw.textsize(s, font=font)
    return (0,0,w,h)

def _wrap_lines(draw, text, font, max_w):
    """Wrap text to fit width - improved word wrapping"""
    if not text or not text.strip():
        return [""]
    
    words = text.split()
    lines, cur = [], []
    def w(ws): return _text_box(draw, " ".join(ws), font)[2] if ws else 0
    
    for word in words:
        # Handle very long single words by breaking them
        while word and w([word]) > max_w:
            # Find how many characters fit
            for i in range(len(word)-1, 0, -1):
                if w([word[:i] + "-"]) <= max_w:
                    if cur:
                        lines.append(" ".join(cur))
                        cur = []
                    lines.append(word[:i] + "-")
                    word = word[i:]
                    break
            else:
                # If even one character doesn't fit, just use it
                if cur:
                    lines.append(" ".join(cur))
                    cur = []
                lines.append(word[:1])
                word = word[1:]
        
        if word:  # If there's still word left
            trial = cur + [word]
            if not cur or w(trial) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(" ".join(cur))
                cur = [word]
    
    if cur: 
        lines.append(" ".join(cur))
    
    return lines if lines else [""]

def _bolt_points(x, y, s):
    """Polygon points for a bolt - exact from approved format"""
    return [
        (x, y),
        (x + s*0.50, y),
        (x + s*0.25, y + s*0.50),
        (x + s*0.72, y + s*0.50),
        (x + s*0.22, y + s*1.20),
        (x + s*0.36, y + s*0.72),
        (x, y + s*0.72),
    ]

def _draw_bolt_outline(draw, pts, width=3):
    """Outline only (hollow) bolt using connected lines - exact from approved format"""
    for i in range(len(pts)):
        a = pts[i]
        b = pts[(i+1) % len(pts)]
        draw.line([a, b], fill=0, width=width)

def _draw_bolt(draw, x, y, s, filled=False):
    """Draw bolt hollow or filled - exact from approved format"""
    pts = _bolt_points(x, y, s)
    if filled:
        draw.polygon(pts, fill=0)
        _draw_bolt_outline(draw, pts, width=3)
    else:
        _draw_bolt_outline(draw, pts, width=3)

def _draw_plus_badge(draw, x, y, w=40, h=40, filled=False):
    """Draw + badge hollow or filled - exact from approved format"""
    r = 6
    # outline rounded rect
    draw.rounded_rectangle([x, y, x+w, y+h], radius=r, outline=0, width=2)
    if filled:
        draw.rounded_rectangle([x+2, y+2, x+w-2, y+h-2], radius=r-2, fill=0)
        bar_color = 255  # invert bars for contrast on filled bg
    else:
        bar_color = 0
    # draw "+"
    pad = 10
    cx = x + w//2
    cy = y + h//2
    draw.rectangle([cx-1, y+pad, cx+1, y+h-pad], fill=bar_color)
    draw.rectangle([x+pad, cy-1, x+w-pad, cy+1], fill=bar_color)

def _draw_bolts_row(draw, y, level, plus=False):
    """Three hollow bolts; fill first `level`; optional + badge at end - exact from approved format"""
    s = 48
    spacing = 20
    total_w = s*3 + spacing*2 + (s + spacing if True else 0)  # include space for plus badge
    start_x = (PAPER_DOTS - total_w) // 2
    for i in range(3):
        _draw_bolt(draw, start_x + i*(s+spacing), y, s=s, filled=(i < max(0, min(3, level))))
    # plus badge
    px = start_x + 3*(s+spacing)
    _draw_plus_badge(draw, px, y + int(s*0.10), w=s, h=s, filled=plus)
    return y + s + 6

def _hr(draw, y, thick=2, inset=0):
    """Horizontal rule - exact from approved format"""
    draw.rectangle([MARGIN_X+inset, y, PAPER_DOTS-MARGIN_X-inset, y+thick], fill=0)

def _draw_wrapped(draw, text, font, y, left_x, right_x):
    """Draw wrapped text - exact from approved format"""
    max_w = right_x - left_x
    for line in _wrap_lines(draw, text, font, max_w):
        draw.text((left_x, y), line, fill=0, font=font)
        y += int(font.size * 1.35)
    return y

def _draw_body(draw, y, body_text):
    """Draw body with checkboxes - exact from approved format"""
    FONT_BODY = _load_font(BODY_PT)
    box = int(FONT_BODY.size * 0.78)
    left_x = MARGIN_X
    right_x = PAPER_DOTS - MARGIN_X
    for raw in body_text.splitlines():
        if raw.startswith("- "):
            # checkbox
            by = y + 3
            draw.rectangle([left_x, by, left_x+box, by+box], outline=0, width=2)
            y = _draw_wrapped(draw, raw[2:].strip(), FONT_BODY, y, left_x + box + 10, right_x)
        elif raw.strip() == "":
            y += int(FONT_BODY.size * 0.6)
        else:
            y = _draw_wrapped(draw, raw, FONT_BODY, y, left_x, right_x)
    return y

def _calculate_due_ranges(due_mode, due_date):
    """Calculate explicit date ranges for due buckets - exact from patch brief"""
    from datetime import date, timedelta
    
    if due_mode == "THIS_WEEK":
        today = date.today()
        start = today - timedelta(days=today.weekday())  # Monday of this week
        end = start + timedelta(days=6)  # Sunday of this week
        return f"DUE: THIS WEEK\n{start.strftime('%a %b %d')} – {end.strftime('%a %b %d')}"
    
    elif due_mode == "NEXT_WEEK":
        today = date.today()
        start = today - timedelta(days=today.weekday()) + timedelta(weeks=1)  # Monday of next week
        end = start + timedelta(days=6)  # Sunday of next week
        return f"DUE: NEXT WEEK\n{start.strftime('%a %b %d')} – {end.strftime('%a %b %d')}"
    
    elif due_mode == "THIS_MONTH":
        today = date.today()
        start = today.replace(day=1)  # First day of month
        if start.month == 12:
            next_month = start.replace(year=start.year+1, month=1, day=1)
        else:
            next_month = start.replace(month=start.month+1, day=1)
        end = next_month - timedelta(days=1)  # Last day of month
        return f"DUE: THIS MONTH\n{start.strftime('%Y-%m-%d')} – {end.strftime('%Y-%m-%d')}"
    
    elif due_mode == "DATE" and due_date:
        return f"DUE: DATE: {due_date.strftime('%Y-%m-%d')}"
    
    else:
        return "DUE: NONE"

def _make_qr(ticket_id, size=80):
    """Generate QR code - exact from approved format"""
    from PIL import Image, ImageDraw
    try:
        import qrcode
        qr = qrcode.QRCode(border=1, box_size=2)
        qr.add_data(f"TICKET:{ticket_id}")
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("L")
        return img.resize((size, size), Image.NEAREST)
    except Exception:
        # Fallback if qrcode not available
        img = Image.new("L", (size, size), 255)
        d = ImageDraw.Draw(img)
        d.rectangle([0,0,size-1,size-1], outline=0, width=3)
        font_small = _load_font(SMALL_PT)
        d.text((6, size//2-6), ticket_id[:8], fill=0, font=font_small)
        return img

def _render_adhd_ticket(ticket_id, title, body, urgency_level, urgency_plus, due_mode, due_date, author, tag):
    """Render ADHD ticket with exact approved format"""
    from PIL import Image, ImageDraw
    from datetime import date
    
    logger.info(f"ESCPOS: Rendering ADHD format for ticket {ticket_id}")
    logger.info(f"ESCPOS: Config - PAPER_DOTS:{PAPER_DOTS}, MARGIN_X:{MARGIN_X}")
    
    # Load fonts
    FONT_TITLE = _load_font(TITLE_PT)
    FONT_LABEL = _load_font(LABEL_PT)
    FONT_BODY = _load_font(BODY_PT)
    FONT_SMALL = _load_font(SMALL_PT)
    
    # Create canvas
    canvas = Image.new("L", (PAPER_DOTS, 1400), 255)
    draw = ImageDraw.Draw(canvas)
    y = 8
    
    # Header row - exact from approved format
    draw.text((MARGIN_X, y), "⚡ ToDo Ticket", fill=0, font=FONT_LABEL)
    ds = date.today().isoformat()
    ds_w = _text_box(draw, ds, FONT_LABEL)[2]
    draw.text((PAPER_DOTS - MARGIN_X - ds_w, y), ds, fill=0, font=FONT_LABEL)
    y += int(FONT_LABEL.size * 1.6)
    
    # Ticket pill - exact from approved format
    pill_txt = f"TICKET #{ticket_id[:8]}"
    l,t,r,b = _text_box(draw, pill_txt, FONT_SMALL)
    pad_x, pad_y = 10, 4
    draw.rounded_rectangle(
        [MARGIN_X, y, MARGIN_X + (r-l) + pad_x*2, y + (b-t) + pad_y*2],
        radius=10, outline=0, width=2
    )
    draw.text((MARGIN_X + pad_x, y + pad_y), pill_txt, fill=0, font=FONT_SMALL)
    y += (b-t) + pad_y*2 + 6
    
    # Title (WRAPPED) - much bigger and prominent
    effective_title = title if title else body.splitlines()[0][:50] if body else "Untitled Ticket"
    y = _draw_wrapped(draw, effective_title, FONT_TITLE, y, MARGIN_X, PAPER_DOTS - MARGIN_X)
    
    # DUE (single literal value with ranges; WRAPPED) - exact from patch brief
    due_text = _calculate_due_ranges(due_mode, due_date)
    y += 4
    y = _draw_wrapped(draw, due_text, FONT_SMALL, y, MARGIN_X, PAPER_DOTS - MARGIN_X)
    
    _hr(draw, y, thick=3); y += 10
    
    # Body (bullets + prose, fully wrapped) - exact from approved format
    y = _draw_body(draw, y, body)
    
    y += 6
    _hr(draw, y, thick=3); y += 10
    
    # Footer with QR code - exact from approved format + patch brief
    left = f"AUTHOR: {author or 'Unknown'}"
    right = f"TAG: {tag or 'None'}"
    draw.text((MARGIN_X, y), left, fill=0, font=FONT_LABEL)
    rw = _text_box(draw, right, FONT_LABEL)[2]
    draw.text((PAPER_DOTS - MARGIN_X - rw, y), right, fill=0, font=FONT_LABEL)
    
    # QR code bottom-left above footer rule
    qr = _make_qr(ticket_id, size=80)
    canvas.paste(qr, (MARGIN_X, y + int(FONT_LABEL.size * 1.5)))
    
    y += int(FONT_LABEL.size * 1.5) + 80  # Account for QR code height
    y += 10  # Extra spacing before urgency bolts
    
    # URGENCY bolts at bottom for visual impact
    draw.text((MARGIN_X, y), "URGENCY", fill=0, font=FONT_LABEL)
    right_lbl = ["NONE","LOW","HIGH","CRITICAL"][max(0, min(3, urgency_level))]
    rw = _text_box(draw, right_lbl, FONT_LABEL)[2]
    draw.text((PAPER_DOTS - MARGIN_X - rw, y), right_lbl, fill=0, font=FONT_LABEL)
    y += int(FONT_LABEL.size * 1.2)
    
    # Bolts + plus at bottom for maximum visibility
    y = _draw_bolts_row(draw, y, urgency_level, plus=urgency_plus)
    y += 8  # Extra spacing at bottom
    
    # Crop to content
    used_h = max(y, 280)
    ticket_bitmap = canvas.crop((0, 0, PAPER_DOTS, used_h)).convert("1")
    
    logger.info(f"ESCPOS: Generated ADHD bitmap ({PAPER_DOTS}x{used_h}px)")
    return ticket_bitmap

def _escpos_print_ticket(ticket, urgency_plus=False, tag=None, due_mode="NONE") -> PrintResult:
    logger.info(f"ESCPOS: Starting print job for ticket {ticket.id}")
    
    try:
        p = _escpos_connect()
        logger.info("ESCPOS: Printer connection established")
        
        try:
            # Map ticket data to expected format
            urgency_level = {"none": 0, "low": 1, "normal": 2, "high": 3, "critical": 3}.get(ticket.urgency.value, 2)
            
            # Due date handling
            due_date_obj = None
            if due_mode == "DATE" and ticket.due_date:
                from datetime import datetime
                if isinstance(ticket.due_date, str):
                    try:
                        due_date_obj = datetime.fromisoformat(ticket.due_date).date()
                    except:
                        pass
            
            # Render with exact approved format
            logger.info("ESCPOS: Rendering ADHD ticket bitmap...")
            ticket_bitmap = _render_adhd_ticket(
                ticket_id=ticket.id[:8],
                title=ticket.title,
                body=ticket.body,
                urgency_level=urgency_level,
                urgency_plus=urgency_plus,
                due_mode=due_mode,
                due_date=due_date_obj,
                author="Corey",  # From patch brief
                tag=tag or "None"
            )
            
            # Edge-to-edge printing setup - exact from approved format
            logger.info("ESCPOS: Setting up edge-to-edge printing...")
            try:
                p.set(align="left")
                # GS L: Set left margin = 0
                p._raw(b"\x1D\x4C\x00\x00")
                # GS W: Set print area width = 576 (0x0240 little-endian)
                p._raw(b"\x1D\x57\x40\x02")
                logger.info("ESCPOS: Edge-to-edge commands sent")
            except Exception as e:
                logger.warning(f"ESCPOS: Edge-to-edge setup failed (safe to ignore): {e}")
            
            # Print bitmap - exact from approved format
            logger.info("ESCPOS: Sending bitmap to printer...")
            try:
                p.image(ticket_bitmap)
                logger.info("ESCPOS: Bitmap sent via p.image()")
            except Exception:
                logger.warning("ESCPOS: p.image() failed, trying p.graphics() fallback...")
                p.graphics(ticket_bitmap)
                logger.info("ESCPOS: Bitmap sent via p.graphics()")
            
            # Final spacing and cut
            logger.info("ESCPOS: Adding final spacing and cut...")
            p.text("\n")
            p.cut()
            logger.info("ESCPOS: Cut command sent successfully")
            
            result = PrintResult(backend="escpos", job_id=str(ticket.id))
            logger.info(f"ESCPOS: Print job completed successfully for ticket {ticket.id}")
            return result
            
        except Exception as e:
            logger.error(f"ESCPOS: Print operation failed for ticket {ticket.id}: {e}")
            raise
        finally:
            try:
                logger.info("ESCPOS: Closing printer connection...")
                p.close()
                logger.info("ESCPOS: Printer connection closed")
            except Exception as e:
                logger.warning(f"ESCPOS: Error closing printer connection: {e}")
                
    except Exception as e:
        logger.error(f"ESCPOS: Print job failed for ticket {ticket.id}: {e}")
        raise

# ---------- Public API ----------

def print_ticket(ticket, html: str, output_dir: Optional[Path] = None, urgency_plus: bool = False, tag: Optional[str] = None, due_mode: str = "NONE") -> dict:
    """
    Unified print entry point.
    
    Args:
        ticket: Ticket model instance
        html: HTML content to print/render
        output_dir: Optional output directory (for file backend)
        
    Returns:
        dict with keys: job_id (str|int|None), pdf_path (Path|None), backend (str)
    """
    logger.info(f"PRINT: Starting print job for ticket {ticket.id} using backend '{PRINT_BACKEND}'")
    
    if PRINT_BACKEND == "file":
        logger.info(f"PRINT: Using file backend for ticket {ticket.id}")
        # Use output_dir or archive path
        if output_dir:
            pdf_path = output_dir / f"ticket-{ticket.id}.pdf"
        else:
            archive_pdf, _ = archive_paths(ticket.id)
            pdf_path = archive_pdf
            
        logger.info(f"PRINT: Target PDF path: {pdf_path}")
        
        # Ensure directory exists
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"PRINT: Created directory: {pdf_path.parent}")
        
        # Try to generate PDF, but don't fail if WeasyPrint has issues (like on older Pi)
        try:
            logger.info("PRINT: Attempting PDF generation with WeasyPrint...")
            from weasyprint import HTML
            HTML(string=html, base_url=".").write_pdf(str(pdf_path))
            logger.info(f"PRINT: PDF generated successfully: {pdf_path}")
            return {
                "job_id": None,
                "pdf_path": pdf_path,
                "backend": "file"
            }
        except ImportError:
            logger.error("PRINT: WeasyPrint not available")
            raise RuntimeError("WeasyPrint not available - install it for PDF generation")
        except Exception as e:
            # WeasyPrint failed (common on Pi due to system library incompatibilities)
            # Return success anyway - this allows thermal printing to work
            logger.warning(f"PRINT: PDF generation failed: {e}")
            return {
                "job_id": None,
                "pdf_path": None,  # No PDF generated
                "backend": "file_no_pdf"
            }

    elif PRINT_BACKEND == "escpos":
        logger.info(f"PRINT: Using ESC/POS backend for ticket {ticket.id}")
        try:
            result = _escpos_print_ticket(ticket, urgency_plus=urgency_plus, tag=tag, due_mode=due_mode)
            logger.info(f"PRINT: ESC/POS print completed successfully for ticket {ticket.id}")
            return {
                "job_id": result.job_id,
                "pdf_path": None,
                "backend": "escpos"
            }
        except Exception as e:
            logger.error(f"PRINT: ESC/POS print failed for ticket {ticket.id}: {e}")
            raise

    else:
        logger.error(f"PRINT: Unknown backend '{PRINT_BACKEND}' for ticket {ticket.id}")
        raise ValueError(f"Unknown PRINT_BACKEND: {PRINT_BACKEND}")
