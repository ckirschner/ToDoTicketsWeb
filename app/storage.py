from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional
import json
import hashlib
import os

ARCHIVE_ROOT = Path("./archives")  # override with ENV/prod settings

def archive_paths(ticket_id: str) -> Tuple[Path, Path]:
    now = datetime.utcnow()
    base = ARCHIVE_ROOT / f"{now:%Y}" / f"{now:%m}" / f"{now:%d}" / ticket_id
    pdf = base / "ticket.pdf"
    meta = base / "ticket.json"
    return pdf, meta

def write_metadata(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def output_pdf_path(job_name: str) -> Path:
    """Generate output path for non-archive PDFs (e.g., temp/preview files)"""
    output_dir = Path(os.getenv("OUTPUT_DIR", "_out"))
    output_dir.mkdir(exist_ok=True)
    return output_dir / f"{job_name}.pdf"

def compute_hash(pdf_path: Optional[Path], json_path: Path) -> str:
    """Compute SHA-256 hash of PDF and JSON files combined"""
    hasher = hashlib.sha256()
    
    # Hash PDF content if it exists
    if pdf_path and pdf_path.exists():
        with open(pdf_path, 'rb') as f:
            hasher.update(f.read())
    else:
        # If no PDF, hash a placeholder string
        hasher.update(b"NO_PDF_GENERATED")
    
    # Hash JSON content
    if json_path.exists():
        with open(json_path, 'rb') as f:
            hasher.update(f.read())
            
    return hasher.hexdigest()
