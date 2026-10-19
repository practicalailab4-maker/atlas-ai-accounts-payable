# Atlas — AI Accounts Payable Employee

**Atlas** is a working prototype of an AI-assisted accounts payable application. It helps turn PDF invoices into structured, reviewable records, checks invoice calculations, and tracks invoice decisions and activity.

> **Project status:** Working prototype for learning and demonstrations. Atlas is not a production accounting system and does not make payments or replace human approval.

## Features

- **PDF invoice upload:** Submit invoices through the web interface (PDFs up to 10 MB).
- **AI-powered extraction:** Uses OpenAI to identify vendor, invoice number, invoice and due dates, bill-to information, currency, line items, subtotal, tax, and total.
- **Invoice validation:** Checks invoice calculations and reports issues for review.
- **Invoice management:** Stores invoices and their details in SQLite and displays them in a browser.
- **Review workflow:** Supports invoice status changes, including approval and rejection.
- **Activity history:** Records new uploads and status changes, with timestamps, and shows the history on the invoice details page.
- **Source document access:** Links each invoice to its original uploaded PDF.

## Technology stack

| Component | Technology |
| --- | --- |
| Backend and API | Python, FastAPI |
| AI extraction | OpenAI API (`gpt-4.1-mini`) |
| Database | SQLite |
| PDF text extraction | `pypdf` |
| Data models | Pydantic |
| Frontend | HTML, JavaScript |
| Development | VS Code, Git, GitHub |

## How it works

1. A user uploads a PDF invoice.
2. Atlas extracts readable text from the PDF.
3. The OpenAI model converts the text into structured invoice fields.
4. Atlas checks the invoice's calculations and flags potential discrepancies.
5. The invoice, validation results, and upload activity are saved to SQLite.
6. A reviewer can inspect the invoice, view the original PDF, and change its status.
7. Atlas records status changes in the invoice's activity history.

## Running locally

### Prerequisites

- Python 3 and `pip`
- An OpenAI API key with API access
- A local copy of this repository

### Setup

From the project directory, create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows, activate with `.venv\Scripts\activate` instead.

Install the project's dependencies using its existing dependency configuration (for example, if `requirements.txt` is present):

```bash
python -m pip install -r requirements.txt
```

Configure your OpenAI API key using the method supported by `backend/ai_client.py`. For example, if it reads the standard environment variable:

```bash
export OPENAI_API_KEY="your-api-key"
```

Do **not** commit API keys, `.env` files containing secrets, or invoice data to GitHub.

Start the FastAPI development server:

```bash
python -m uvicorn backend.main:app --reload
```

Then open **http://127.0.0.1:8000/** in your browser. API documentation, if enabled, is typically available at **http://127.0.0.1:8000/docs**.

> **Note:** Dependency installation and API-key configuration should be checked against the files in your local checkout before using this as a fresh-install guide.

## Demo walkthrough

For a short demonstration video:

1. Open the Atlas web application.
2. Upload a sample PDF invoice with a **new invoice number**.
3. Open the resulting invoice details page.
4. Show the extracted fields, totals, and validation issues.
5. Show the original PDF link.
6. Change the invoice's review status.
7. Show the Activity History entries for the upload and status change.

Use fictional or redacted invoice data in recordings. Avoid exposing API keys, private file paths, or customer information.

## Current limitations

- **Human review is still required.** AI extraction can be imperfect, especially for unusual layouts or ambiguous invoice text.
- **Text-based PDFs work best.** Scanned PDFs without selectable text are not supported by the current extraction approach unless OCR is added.
- **Invoice totals should be verified.** A simple test PDF produced a zero-value extraction during testing; existing sample invoices displayed correct values.
- **Local-first storage.** SQLite and local PDF storage are suitable for prototyping, not a hardened multi-user production deployment.
- **No payment execution or accounting-system integration** is claimed.

## Possible future improvements

- OCR for scanned invoices
- Better handling of diverse invoice layouts and extraction confidence
- Duplicate-invoice review and more robust error handling
- Authentication, user roles, and audit controls
- Integrations with accounting platforms
- Automated tests and production deployment safeguards

## Project purpose

Atlas demonstrates how AI can assist with a real business workflow by combining document processing, structured extraction, validation, a review interface, and activity tracking.

**Built as a practical AI automation project and demonstration.**
