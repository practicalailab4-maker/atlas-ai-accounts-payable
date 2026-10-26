import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from fastapi.responses import Response

import sqlite3
import tempfile
import uuid
from pathlib import Path
from fastapi.responses import FileResponse

from fastapi import FastAPI, UploadFile, File, HTTPException
from starlette.concurrency import run_in_threadpool

from backend.invoice_processor import process_invoice
from backend.excel_export import create_excel_workbook
from backend.database import DATA_DIR, list_invoices, get_invoice, update_invoice_status

app = FastAPI(
    title="Atlas AI Accounts Payable",
    version="0.1.0"
)
INVOICE_DIR = DATA_DIR / "invoices"
INVOICE_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/")
def home():
    return {
        "name": "Atlas",
        "role": "AI Accounts Payable Employee",
        "status": "online",
        "message": "Atlas backend is running successfully!"
    }
@app.get("/invoices/export")
def download_invoice_register():
    excel_path = DATA_DIR / "exports" / "atlas_invoice_register.xlsx"

    create_excel_workbook()

    if not excel_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Invoice register Excel file not found"
        )

    return FileResponse(
        path=excel_path,
        filename="atlas_invoice_register.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


    
@app.get("/invoices/{invoice_id}/pdf")
def view_invoice_pdf(invoice_id: int):
    invoice = get_invoice(invoice_id)

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    pdf_path = Path(invoice["source_file"]).resolve()

    if not pdf_path.is_relative_to(DATA_DIR.resolve()):
        raise HTTPException(
            status_code=403,
            detail="PDF access not permitted"
        )

    if not pdf_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Original PDF file not found"
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        content_disposition_type="inline"
    )
@app.get("/invoice-details")
def invoice_details_page():
    html_path = Path(__file__).resolve().parent.parent / "frontend" / "invoice_details.html"
    return FileResponse(html_path)
@app.get("/dashboard")
def dashboard():
    html_path = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
    return FileResponse(html_path)


@app.get("/invoices")
def get_invoices():
    return list_invoices()


@app.get("/atlas/ap-briefing")
def atlas_ap_briefing():
    from datetime import date
    from decimal import Decimal, InvalidOperation

    invoices = list_invoices()
    today = date.today()

    pending = [
        invoice for invoice in invoices
        if invoice.get("status") == "needs_review"
    ]

    overdue = []
    totals_by_currency = {}

    for invoice in pending:
        due_date = invoice.get("due_date")

        if due_date:
            try:
                if date.fromisoformat(str(due_date)) < today:
                    overdue.append(invoice)
            except ValueError:
                pass

        currency = invoice.get("currency") or "Unknown"

        try:
            amount = Decimal(str(invoice.get("total") or "0"))
            totals_by_currency[currency] = (
                totals_by_currency.get(currency, Decimal("0")) + amount
            )
        except InvalidOperation:
            pass

    return {
        "as_of": today.isoformat(),
        "pending_review_count": len(pending),
        "overdue_pending_count": len(overdue),
        "pending_amounts_by_currency": {
            currency: str(amount)
            for currency, amount in totals_by_currency.items()
        },
        "message": (
            f"You have {len(pending)} invoices awaiting review, "
            f"including {len(overdue)} overdue invoices."
        )
    }


@app.get("/invoices/{invoice_id}")
def get_invoice_by_id(invoice_id: int):
    return get_invoice(invoice_id)

@app.patch("/invoices/{invoice_id}/status")
def change_invoice_status(invoice_id: int, status: str):
    if status not in ("needs_review", "approved", "rejected"):
        raise HTTPException(
            status_code=400,
            detail="Invalid invoice status"
        )

    updated = update_invoice_status(invoice_id, status)

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found"
        )

    return {"invoice_id": invoice_id, "status": status}


@app.post("/invoices/upload")
async def upload_invoice(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF invoices are supported."
        )

    header = await file.read(5)

    if header != b"%PDF-":
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid PDF."
        )
    await file.seek(0)

    pdf_content = await file.read(10 * 1024 * 1024 + 1)

    if len(pdf_content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="PDF file exceeds the 10 MB limit."
        )

    with tempfile.NamedTemporaryFile(
        suffix=".pdf",
        delete=False
    ) as temporary_file:
        temporary_file.write(pdf_content)
        temporary_path = Path(temporary_file.name)
    permanent_path = INVOICE_DIR / f"{uuid.uuid4().hex}.pdf"

    try:
        temporary_path.replace(permanent_path)
        invoice_id = await run_in_threadpool(process_invoice, str(permanent_path))
        invoice_details = get_invoice(invoice_id) or {}

        return {
            "filename": file.filename,
            "invoice_id": invoice_id,
            "vendor_name": invoice_details.get("vendor_name"),
            "invoice_number": invoice_details.get("invoice_number"),
            "total": invoice_details.get("total"),
            "currency": invoice_details.get("currency"),
            "validation_issues": invoice_details.get("validation_issues", []),
            "status": "needs_review",
            "message": "Atlas processed and saved the invoice successfully."
            
        }

    except sqlite3.IntegrityError:
        permanent_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409,
            detail="This invoice already exists in Atlas."
        )
    except Exception:
        permanent_path.unlink(missing_ok=True)
        raise
    finally:
        temporary_path.unlink(missing_ok=True)


# Atlas AI employee voice — ElevenLabs
@app.post("/atlas/speak")
def atlas_speak(announcement: str = "", invoice_id: int | None = None):
    import requests

    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=True)

    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID")

    if not api_key or not voice_id:
        raise HTTPException(
            status_code=503,
            detail="Atlas voice is not configured."
        )

    if announcement == "invoice_complete" and invoice_id is not None:
        invoice = get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")

        number = str(invoice.get("invoice_number") or "unknown")
        spoken_number = number.replace("-", " ").replace("_", " ")
        vendor = str(invoice.get("vendor_name") or "unknown vendor")
        total = str(invoice.get("total") or "")
        currency = str(invoice.get("currency") or "")

        message = (
            f"I've processed invoice {spoken_number} from {vendor}"
            + (f" for {total} {currency}" if total and currency else "")
            + ". "
        )

        issues = invoice.get("validation_issues") or []
        if issues:
            message += (
                f"I found {len(issues)} validation "
                "issues that need your attention."
            )
        else:
            message += "It's ready for your review."

    elif announcement == "ap_briefing":
        from decimal import Decimal

        briefing = atlas_ap_briefing()
        pending = briefing["pending_review_count"]
        overdue = briefing["overdue_pending_count"]
        amounts = briefing["pending_amounts_by_currency"]

        message = (
            "Here's your accounts payable briefing. "
            f"You currently have {pending} invoices awaiting review, "
            f"including {overdue} overdue invoices. "
        )

        if len(amounts) == 1 and "USD" in amounts:
            total = Decimal(amounts["USD"])
            from num2words import num2words

            dollars = int(total)
            cents = int((total - dollars) * 100)

            spoken_amount = f"{num2words(dollars)} dollars"

            if cents:
                spoken_amount += f" and {num2words(cents)} cents"

            message += (
                f"The total value of invoices awaiting review is "
                f"{spoken_amount}. "
                "This amount excludes invoices that have already "
                "been approved. "
            )

        if overdue:
            message += (
                "I recommend prioritizing the overdue invoices "
                "for review and approval to avoid further payment delays. "
            )

        message += (
            "Once approved, eligible invoices can move into "
            "the payment queue. I'll continue monitoring "
            "your outstanding payables."
        )

    elif announcement == "invoice_complete":
        message = "I've finished processing your invoice. It's ready for review."
    else:
        message = (
            "Hello! I'm Atlas, your AI Accounts Payable Employee. "
            "I'm ready to process your invoices. "
            "Please upload your invoice whenever you're ready, "
            "and I'll process it as soon as it's uploaded."
        )

    try:
        result = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": message,
                "model_id": "eleven_flash_v2_5",
            },
            timeout=30,
        )
        result.raise_for_status()
    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="Atlas could not generate speech. Check ElevenLabs settings."
        )

    return Response(content=result.content, media_type="audio/mpeg")
