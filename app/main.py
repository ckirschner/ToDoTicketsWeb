from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .deps import init_db, get_db
from .schemas import TicketCreate
from .models import Ticket, Urgency
from .printing import print_ticket
from .storage import archive_paths, write_metadata, compute_hash
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import Optional
import os
import shutil
import logging

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available, environment variables must be set externally

# Configure main app logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="ToDo Tickets Web")

# Static and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/views")

@app.on_event("startup")
def _startup() -> None:
    init_db()

@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def create_form(request: Request):
    return templates.TemplateResponse("create.html", {"request": request})

# Minimal create -> (later) render/print/archive
def _resolve_due(due_quick: Optional[str], due_date_str: Optional[str]) -> Optional[str]:
    """Resolve quick due date options to actual ISO dates"""
    if due_quick == "custom" and due_date_str:
        return due_date_str
    if due_quick == "today":
        return date.today().isoformat()
    if due_quick == "this_week":
        # next Sunday (assuming Mon–Sun workweek; adjust if you prefer)
        today = date.today()
        days = (6 - today.weekday()) % 7
        return (today + timedelta(days=days)).isoformat()
    if due_quick == "next_week":
        today = date.today()
        # Monday of next week
        days = (7 - today.weekday()) % 7
        return (today + timedelta(days=days)).isoformat()
    if due_quick == "this_month":
        today = date.today()
        # last day of month
        first_next = (date(today.year + (today.month==12), (today.month % 12)+1, 1))
        return (first_next - timedelta(days=1)).isoformat()
    return None

def _infer_title(title: Optional[str], body: str) -> str:
    """Infer title from first line of body if not provided"""
    if title and title.strip():
        return title.strip()
    first = (body.splitlines()[0] if body else "").strip()
    if 0 < len(first) <= 50:
        return first
    return f"Ticket {datetime.now():%Y-%m-%d %H:%M}"

def _map_urgency(u: str) -> Urgency:
    """Safely map urgency string to enum"""
    try:
        return Urgency(u)
    except Exception:
        return Urgency.normal

@app.post("/api/tickets")
def create_ticket(
    request: Request,
    title: Optional[str] = Form(None),
    body: str = Form(...),
    urgency: str = Form("none"),
    urgency_plus: bool = Form(False),
    tag: Optional[str] = Form(None),
    due_quick: Optional[str] = Form(None),
    due_date: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # Map due_quick to patch brief modes and resolve due date
    due_mode_map = {
        "today": "DATE",
        "this_week": "THIS_WEEK",
        "next_week": "NEXT_WEEK", 
        "this_month": "THIS_MONTH",
        "custom": "DATE"
    }
    due_mode = due_mode_map.get(due_quick, "NONE")
    resolved_due = _resolve_due(due_quick, due_date)
    final_title = _infer_title(title, body)
    
    # Create ticket record
    ticket = Ticket(
        title=final_title,
        body=body,
        urgency=_map_urgency(urgency),
        due_date=resolved_due,
        archive_pdf_path="",
        archive_json_path="",
        hash="",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)  # Get the generated ID
    
    # Build HTML content for printing
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ticket {ticket.id}</title>
        <style>
            body {{ font-family: monospace; font-size: 12px; }}
            .header {{ text-align: center; font-weight: bold; }}
            .urgency {{ text-transform: uppercase; }}
        </style>
    </head>
    <body>
        <div class="header">Ticket #{ticket.id}</div>
        <h2>{ticket.title}</h2>
        <p><strong>Urgency:</strong> <span class="urgency">{ticket.urgency.value}</span></p>
        {f'<p><strong>Due:</strong> {ticket.due_date}</p>' if ticket.due_date else ''}
        <p><strong>Created:</strong> {ticket.created_at.strftime('%Y-%m-%d %H:%M')}</p>
        <hr>
        <div>{ticket.body}</div>
        <hr>
        <p style="text-align: center;">toDoTickets</p>
    </body>
    </html>
    """
    
    try:
        logger.info(f"MAIN: Starting print/archive process for ticket {ticket.id}")
        
        # Print the ticket
        logger.info(f"MAIN: Calling print_ticket for ticket {ticket.id}")
        print_result = print_ticket(ticket, html_content, urgency_plus=urgency_plus, tag=tag, due_mode=due_mode)
        logger.info(f"MAIN: print_ticket returned: {print_result}")
        
        # Set up archive paths
        archive_pdf_path, archive_json_path = archive_paths(ticket.id)
        logger.info(f"MAIN: Archive paths - PDF: {archive_pdf_path}, JSON: {archive_json_path}")
        
        # Write metadata
        metadata = {
            "id": ticket.id,
            "title": ticket.title,
            "body": ticket.body,
            "urgency": ticket.urgency.value,
            "urgency_plus": urgency_plus,
            "tag": tag,
            "due_date": ticket.due_date,
            "due_mode": due_mode,
            "created_at": ticket.created_at.isoformat(),
            "printed_at": datetime.utcnow().isoformat(),
            "print_backend": print_result["backend"],
            "job_id": print_result["job_id"]
        }
        logger.info(f"MAIN: Writing metadata for ticket {ticket.id}")
        write_metadata(archive_json_path, metadata)
        logger.info(f"MAIN: Metadata written successfully")
        
        # For file backend, copy PDF to archive location if needed
        pdf_archived = False
        if print_result["pdf_path"] and print_result["pdf_path"] != archive_pdf_path:
            logger.info(f"MAIN: Copying PDF from {print_result['pdf_path']} to {archive_pdf_path}")
            archive_pdf_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(print_result["pdf_path"], archive_pdf_path)
            pdf_archived = True
            logger.info("MAIN: PDF copied successfully")
        elif print_result["pdf_path"] == archive_pdf_path:
            pdf_archived = True
            logger.info("MAIN: PDF already at archive location")
        else:
            logger.info("MAIN: No PDF to archive (ESC/POS backend or PDF generation failed)")
        
        # Compute hash and update ticket 
        logger.info(f"MAIN: Computing hash for ticket {ticket.id}")
        ticket_hash = compute_hash(archive_pdf_path if pdf_archived else None, archive_json_path)
        ticket.archive_pdf_path = str(archive_pdf_path) if pdf_archived else ""
        ticket.archive_json_path = str(archive_json_path)
        ticket.hash = ticket_hash
        ticket.printed_at = datetime.utcnow()
        ticket.print_job_id = print_result["job_id"]
        ticket.status = "printed"
        
        logger.info(f"MAIN: Updating ticket {ticket.id} with status 'printed'")
        db.commit()
        logger.info(f"MAIN: Ticket {ticket.id} processed successfully")
        
    except Exception as e:
        # If printing/archiving fails, mark ticket as failed but keep it
        logger.error(f"MAIN: Print/archive process failed for ticket {ticket.id}: {e}")
        logger.error(f"MAIN: Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"MAIN: Full traceback: {traceback.format_exc()}")
        
        ticket.status = "failed"
        db.commit()
        logger.info(f"MAIN: Ticket {ticket.id} marked as failed")
        
    return RedirectResponse(url="/", status_code=303)

@app.get("/history", response_class=HTMLResponse)
def history(request: Request, db: Session = Depends(get_db)):
    items = db.query(Ticket).order_by(Ticket.created_at.desc()).limit(100).all()
    return templates.TemplateResponse("history.html", {"request": request, "items": items})

@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    # Get system information
    print_backend = os.getenv("PRINT_BACKEND", "file")
    archive_dir = os.getenv("ARCHIVE_DIR", "archives")
    output_dir = os.getenv("OUTPUT_DIR", "_out")
    
    # Connection info for ESC/POS
    connection_info = None
    if print_backend == "escpos":
        conn_type = os.getenv("ESCPOS_CONNECTION", "network")
        if conn_type == "network":
            host = os.getenv("ESCPOS_HOST", "127.0.0.1")
            port = os.getenv("ESCPOS_PORT", "9100")
            connection_info = f"Network: {host}:{port}"
        elif conn_type == "usb":
            vid = os.getenv("ESCPOS_VENDOR_ID", "0000")
            pid = os.getenv("ESCPOS_PRODUCT_ID", "0000")
            connection_info = f"USB: VID={vid}, PID={pid}"
        elif conn_type == "serial":
            device = os.getenv("ESCPOS_DEVICE", "/dev/ttyUSB0")
            baudrate = os.getenv("ESCPOS_BAUDRATE", "9600")
            connection_info = f"Serial: {device} @ {baudrate} baud"
    
    # Disk usage for archive directory
    disk_info = None
    try:
        if os.path.exists(archive_dir):
            total, used, free = shutil.disk_usage(archive_dir)
            disk_info = {
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "used_percent": round((used / total) * 100, 1)
            }
    except Exception:
        pass
    
    admin_data = {
        "print_backend": print_backend,
        "archive_dir": archive_dir,
        "output_dir": output_dir,
        "connection_info": connection_info,
        "disk_info": disk_info
    }
    
    return templates.TemplateResponse("admin.html", {"request": request, "admin": admin_data})

@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
def ticket_detail(request: Request, ticket_id: str, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return templates.TemplateResponse("detail.html", {"request": request, "ticket": ticket})

@app.post("/tickets/{ticket_id}/delete")
def delete_ticket(request: Request, ticket_id: str, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    db.delete(ticket)
    db.commit()
    return RedirectResponse(url="/history", status_code=303)

