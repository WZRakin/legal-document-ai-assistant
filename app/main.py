from __future__ import annotations

import shutil
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import UPLOAD_DIR, create_document, get_chunks, get_document, init_db, insert_chunks, latest_learning_rules, list_documents, save_edit_learning, update_document
from app.services.chunker import Chunk, chunk_pages
from app.services.llm import extract_structured_fields, generate_grounded_memo, learn_from_edit
from app.services.pdf_processor import extract_pdf_text
from app.services.retriever import TfidfRetriever

app = FastAPI(title="Legal Document AI Portal")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


@app.post("/api/upload")
def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    temp_path = UPLOAD_DIR / safe_name
    with temp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    doc_id = create_document(safe_name, str(temp_path))

    try:
        pages = extract_pdf_text(str(temp_path))
        full_text = "\n\n".join([f"[Page {p.page}]\n{p.text}" for p in pages])
        chunks = chunk_pages(pages)
        chunk_dicts = [asdict(c) for c in chunks]
        insert_chunks(doc_id, chunk_dicts)

        extracted = extract_structured_fields(full_text)
        update_document(doc_id, status="processed", extracted_text=full_text, extracted_json=extracted)
        return {"document_id": doc_id, "status": "processed", "pages": len(pages), "chunks": len(chunks), "extracted": extracted}
    except Exception as exc:
        update_document(doc_id, status="failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/documents")
def documents():
    return list_documents()


@app.get("/api/documents/{document_id}")
def document_detail(document_id: int):
    doc = get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc["chunks"] = get_chunks(document_id)
    return doc


@app.post("/api/documents/{document_id}/retrieve")
def retrieve(document_id: int, query: str = Form(...), top_k: int = Form(5)):
    chunks_raw = get_chunks(document_id)
    if not chunks_raw:
        raise HTTPException(status_code=404, detail="No chunks found for this document")
    chunks = [Chunk(**c) for c in chunks_raw]
    return TfidfRetriever(chunks).search(query, top_k=top_k)


@app.post("/api/documents/{document_id}/generate-draft")
def generate_draft(document_id: int):
    doc = get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks_raw = get_chunks(document_id)
    chunks = [Chunk(**c) for c in chunks_raw]
    retriever = TfidfRetriever(chunks)
    evidence = []
    for q in ["parties effective date key dates payment terms obligations notice breach termination governing law dispute resolution"]:
        evidence.extend(retriever.search(q, top_k=8))

    seen = set()
    unique_evidence = []
    for item in evidence:
        if item["chunk_id"] not in seen:
            unique_evidence.append(item)
            seen.add(item["chunk_id"])

    draft = generate_grounded_memo(doc.get("extracted_json") or {}, unique_evidence[:10])
    update_document(document_id, draft=draft)
    return {"document_id": document_id, "draft": draft, "evidence": unique_evidence[:10]}


@app.post("/api/documents/{document_id}/learn-from-edit")
def learn_edit(document_id: int, edited_draft: str = Form(...)):
    doc = get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    original = doc.get("draft") or ""
    learned = learn_from_edit(original, edited_draft)
    save_edit_learning(document_id, original, edited_draft, learned)
    return {"document_id": document_id, "learned": learned}


@app.get("/api/learning-rules")
def learning_rules():
    return latest_learning_rules()


@app.get("/api/documents/{document_id}/download-draft")
def download_draft(document_id: int):
    doc = get_document(document_id)
    if not doc or not doc.get("draft"):
        raise HTTPException(status_code=404, detail="Draft not found")
    out = UPLOAD_DIR / f"draft_{document_id}.md"
    out.write_text(doc["draft"], encoding="utf-8")
    return FileResponse(str(out), filename=f"draft_{document_id}.md")
