# Legal Document AI Portal

A practical take-home assessment starter for document understanding, grounded drafting, and improvement from operator edits.

## What it does

- Uploads PDF legal-style documents
- Extracts text using PyMuPDF
- Falls back to Tesseract OCR for pages with little/no selectable text
- Cleans and chunks extracted text
- Builds a retrieval layer using local TF-IDF search
- Extracts structured JSON fields with an LLM when `GEMINI_API_KEY` is configured
- Generates a grounded first-pass internal memo from retrieved evidence
- Captures operator edits and extracts reusable improvement rules

## Architecture

```text
PDF Upload
  -> PDF text extraction / OCR fallback
  -> Clean page-level text
  -> Chunking with page references
  -> Local retrieval index
  -> Structured JSON extraction
  -> Evidence retrieval
  -> Grounded memo generation
  -> Operator edit capture
  -> Reusable improvement rules
```

## Why this design

The assessment values grounding and engineering quality more than visual polish. This project therefore separates extraction, retrieval, drafting, and learning into separate services.

The draft generation step does not directly rely on the whole PDF. It first extracts structured fields and retrieves supporting evidence, then drafts from that evidence.

## Setup

### 1. Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Optional OCR setup

For scanned PDFs, install Tesseract:

macOS:

```bash
brew install tesseract
```

Ubuntu:

```bash
sudo apt-get install tesseract-ocr
```

### 4. Add API key

Copy the example file:

```bash
cp .env.example .env
```

Then add:

```bash
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash-lite
```

The app still runs without an API key, but model-based JSON extraction and memo generation will use fallback outputs.

### 5. Run the app

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## API endpoints

### Upload and process PDF

```http
POST /api/upload
```

Form field:

```text
file: PDF
```

### List documents

```http
GET /api/documents
```

### Read document details

```http
GET /api/documents/{document_id}
```

### Retrieve evidence

```http
POST /api/documents/{document_id}/retrieve
```

Form fields:

```text
query: termination notice
 top_k: 5
```

### Generate grounded draft

```http
POST /api/documents/{document_id}/generate-draft
```

### Learn from operator edit

```http
POST /api/documents/{document_id}/learn-from-edit
```

Form field:

```text
edited_draft: edited memo text
```

## Sample output shape

Structured extraction returns fields like:

```json
{
  "document_type": "Service Agreement",
  "parties": [
    {
      "name": "ABC Ltd",
      "role": "Client",
      "evidence": "Page 1"
    }
  ],
  "key_dates": [],
  "obligations": [],
  "payment_terms": [],
  "notice_requirements": [],
  "termination": [],
  "risks": [],
  "missing_information": []
}
```

## Assumptions and tradeoffs

- TF-IDF retrieval is used to keep the project easy to run locally. In production, replace this with embeddings and pgvector, ChromaDB, or FAISS.
- Tesseract OCR is included as a simple fallback. For stronger scanned document handling, use Google Document AI, Azure Document Intelligence, AWS Textract, or Mistral OCR.
- The system is designed for first-pass internal summaries, not final legal advice.
- Every downstream step keeps page/chunk references to support grounding.

## Evaluation approach

Recommended manual evaluation:

1. Upload a clean text PDF and confirm extraction quality.
2. Upload a scanned PDF and confirm OCR fallback behavior.
3. Run retrieval queries such as payment terms, notice, termination, parties.
4. Confirm the generated memo only uses retrieved evidence.
5. Edit the memo and submit the edited draft.
6. Confirm reusable improvement rules are saved.

Suggested metrics:

- Field extraction accuracy
- Number of extracted fields with evidence
- Retrieval precision for key clauses
- Unsupported claims found in draft
- Operator edit reduction over repeated samples

## Future improvements

- Add embedding retrieval with pgvector
- Add document preview with highlighted evidence
- Add DOCX/PDF export
- Add authentication and user-level document storage
- Add test suite with synthetic legal documents
- Add stronger OCR provider for handwritten and low-resolution files
