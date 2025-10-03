from pydantic import BaseModel, Field
from typing import Optional

# For Python 3.7 compatibility - use string literals instead of Literal type
Urgency = str

class TicketCreate(BaseModel):
    title: str = Field(..., max_length=200)
    body: str
    urgency: Urgency = "normal"
    due_date: Optional[str] = None  # YYYY-MM-DD

class TicketRead(BaseModel):
    id: str
    title: str
    body: str
    urgency: Urgency
    due_date: Optional[str]
    status: str
    archive_pdf_path: str
    archive_json_path: str
