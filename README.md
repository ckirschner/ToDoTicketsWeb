# ToDoTicketsWeb 🎫⚡

A specialized ADHD-friendly ticket printing system designed for thermal printers and Raspberry Pi deployment. Create visual, prioritized task tickets with lightning bolt urgency indicators and print them instantly.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-web%20framework-green.svg)

## ✨ Features

### 🧠 ADHD-Optimized Design
- **Visual urgency indicators**: 0-3 hollow lightning bolts that fill based on priority
- **Large, prominent titles** (48pt font) visible from across the room  
- **Lightning bolts at bottom** for maximum visual impact
- **Checkbox support** for task lists (lines starting with `- `)
- **QR codes** for digital integration (`TICKET:<id>` format)

### 🖨️ Thermal Printing
- **ESC/POS thermal printer support** via USB
- **Edge-to-edge printing** on 80mm thermal paper (576px width @ 203dpi)
- **Bitmap rendering** for precise layout control
- **Automatic word wrapping** with intelligent line breaking

### 📅 Smart Scheduling
- **Quick due date options**: This Week, Next Week, This Month
- **Custom date selection** with explicit date range calculations
- **Visual due date display** with clear time boundaries

### 🏷️ Organization
- **Urgency Plus toggle** for enhanced priority marking
- **Custom tags** for categorization
- **Comprehensive history** with expandable ticket details
- **Archive system** with JSON metadata and optional PDF export

### 🔧 Developer-Friendly
- **Raspberry Pi optimized** with automated sync workflow
- **Environment-based configuration** for development and production
- **Comprehensive logging** for debugging print failures
- **RESTful API** with FastAPI framework

## 🚀 Quick Start

### Local Development

1. **Clone and setup:**
   ```bash
   git clone https://github.com/ckirschner/ToDoTicketsWeb.git
   cd ToDoTicketsWeb
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Run locally:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
   ```

3. **Access the application:**
   - Web interface: http://localhost:8001
   - API docs: http://localhost:8001/docs

### Raspberry Pi Deployment

1. **Setup Pi sync configuration:**
   ```bash
   cp .pi_sync.env.example .pi_sync.env
   # Edit .pi_sync.env with your Pi's details
   ```

2. **Deploy to Pi:**
   ```bash
   ./sync_to_pi.sh --test        # Test SSH connection
   ./sync_to_pi.sh --bootstrap   # Install system dependencies
   ./sync_to_pi.sh --install     # Install Python packages
   ./sync_to_pi.sh               # Sync code
   ./sync_to_pi.sh --run         # Start server
   ```

3. **Access on network:**
   - Web interface: http://YOUR_PI_IP:8080
   - Server management: `./sync_to_pi.sh --stop` / `--run`

## 🖨️ Printer Setup

### Supported Printers
- Any ESC/POS compatible thermal printer
- Tested with 80mm thermal paper
- USB connection recommended

### Configuration
1. **Connect printer** to Raspberry Pi via USB
2. **Set environment variables** on Pi:
   ```bash
   echo "PRINT_BACKEND=escpos" > .env
   echo "ESCPOS_DEVICE=/dev/usb/lp0" >> .env
   ```
3. **Install printer dependencies:**
   ```bash
   ./sync_to_pi.sh --install
   ```

### Print Backends
- **ESC/POS**: Direct thermal printing (production)
- **File**: PDF generation for development/testing

## 🎨 Ticket Format

The ADHD-optimized ticket format includes:

```
⚡ ToDo Ticket                    2025-01-01
┌─────────────┐
│ TICKET #ABC │
└─────────────┘

BIG VISIBLE TITLE HERE
(48pt font for distance visibility)

DUE: THIS WEEK
Mon Oct 07 – Sun Oct 13

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Task details and description here.
☐ Checkbox items for tasks
☐ Another task item  
☐ More tasks as needed

Normal paragraph text wraps properly
across multiple lines with intelligent
word breaking for long URLs and text.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AUTHOR: Corey                TAG: Work

[QR CODE]

URGENCY                      HIGH
⚡⚡⚡ +
```

## 📋 API Reference

### Create Ticket
```http
POST /api/tickets
Content-Type: application/x-www-form-urlencoded

title=My Task&body=Task details&urgency=high&urgency_plus=on&tag=Work&due_quick=this_week
```

### View History
```http
GET /history
```

### Admin Dashboard
```http
GET /admin
```

## ⚙️ Configuration

### Environment Variables

**Development (.env):**
```bash
PRINT_BACKEND=file
DATABASE_URL=sqlite:///./tickets.db
OUTPUT_DIR=_out
ARCHIVE_DIR=archives
```

**Production Pi (.env):**
```bash
PRINT_BACKEND=escpos
ESCPOS_DEVICE=/dev/usb/lp0
DATABASE_URL=sqlite:///./tickets.db
ARCHIVE_DIR=archives
```

### Font Configuration
Edit `ticket_print.ini` to customize font sizes:
```ini
[fonts]
title_pt = 48    # Large title for visibility
label_pt = 16    # Section labels
body_pt  = 22    # Main content
small_pt = 18    # Details and metadata
```

## 🛠️ Development Workflow

### Daily Development
```bash
# Make changes locally
# Test with: uvicorn app.main:app --reload

# Sync to Pi when ready
./sync_to_pi.sh

# Server auto-reloads on Pi!
```

### Testing
```bash
# Test specific features
python -c "from app.printing import _render_adhd_ticket; print('Tests passed')"

# Manual testing
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Troubleshooting
```bash
# View Pi server logs
ssh pi@YOUR_PI_IP
tmux attach -t todotickets
# Exit with Ctrl+B then D

# Check printer connection
ls -la /dev/usb/lp*

# Test print backend
curl -X POST "http://YOUR_PI_IP:8080/api/tickets" \
  -d "body=Test print&urgency=normal"
```

## 📁 Project Structure

```
ToDoTicketsWeb/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── models.py            # Database models
│   ├── schemas.py           # Pydantic schemas
│   ├── deps.py              # Dependencies and DB setup
│   ├── printing.py          # ADHD ticket rendering & ESC/POS
│   ├── storage.py           # Archive management
│   ├── static/              # CSS and assets
│   └── views/               # Jinja2 templates
├── requirements.txt         # Python dependencies
├── requirements.pi.txt      # Pi-specific additions
├── sync_to_pi.sh           # Pi deployment script
├── .pi_sync.env.example    # Pi configuration template
├── .env.example            # Environment template
├── ticket_print.ini        # Font configuration
└── README.md
```

## 🔧 System Requirements

### Local Development
- Python 3.7+
- FastAPI, SQLAlchemy, Jinja2
- PIL/Pillow for image generation
- Optional: WeasyPrint for PDF export

### Raspberry Pi Production
- Raspberry Pi OS (Debian-based)
- Python 3.7+
- ESC/POS thermal printer (USB)
- All Python dependencies from requirements.pi.txt

### Recommended Hardware
- Raspberry Pi 4B (2GB+ RAM)
- 80mm thermal printer (ESC/POS compatible)
- MicroSD card (16GB+)
- Reliable power supply

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly (especially print functionality)
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Designed specifically for ADHD task management workflows
- Optimized for thermal printing on Raspberry Pi
- Built with FastAPI for modern Python web development
- ESC/POS printing via python-escpos library

---

**Made with ❤️ for better task management and ADHD-friendly workflows**