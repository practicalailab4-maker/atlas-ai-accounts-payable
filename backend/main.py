import sqlite3
import tempfile
import uuid
from pathlib import Path
from fastapi.responses import FileResponse

from fastapi import FastAPI, UploadFile, File, HTTPException
from starlette.concurrency import run_in_threadpool

from backend.invoice_processor import process_invoice
from backend.database import DATA_DIR, list_invoices, get_invoice

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


@app.get("/invoices/{invoice_id}")
def get_invoice_by_id(invoice_id: int):
    return get_invoice(invoice_id)


@app.post("/invoices/upload")

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

        return {
            "filename": file.filename,
            "invoice_id": invoice_id,
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