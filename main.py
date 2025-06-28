from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import pdfplumber
import pandas as pd
import os
import re

app = FastAPI()

# ✅ SMART INVOICE FIELD EXTRACTOR FUNCTION
def extract_invoice_fields(text):
    fields = {}

    match = re.search(r"Invoice\s*(No|Number)?[:\-]?\s*([A-Z0-9\-]+)", text, re.IGNORECASE)
    if match:
        fields["invoice_number"] = match.group(2)

    date_match = re.search(r"\b(\d{2}[\/\-]\d{2}[\/\-]\d{4}|\d{4}[\/\-]\d{2}[\/\-]\d{2})\b", text)
    if date_match:
        fields["invoice_date"] = date_match.group(0)

    total_match = re.search(r"Total\s*[:\-]?\s*\$?([0-9,.]+)", text, re.IGNORECASE)
    if total_match:
        fields["total_amount"] = total_match.group(1)

    vendor_match = re.search(r"From\s*[:\-]?\s*([A-Za-z0-9 ,.&]+)", text)
    if vendor_match:
        fields["vendor"] = vendor_match.group(1)

    return fields

# ✅ PDF TEXT + TABLE EXTRACTOR
def extract_from_pdf(pdf_path):
    full_text = ""
    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

            tables = page.extract_tables()
            for table in tables:
                all_tables.append(table)

    return full_text, all_tables

# ✅ MAIN EXTRACTION ENDPOINT
@app.post("/extract/")
async def extract(file: UploadFile = File(...)):
    with open("uploaded.pdf", "wb") as f:
        f.write(await file.read())

    text, tables = extract_from_pdf("uploaded.pdf")
    invoice_fields = extract_invoice_fields(text)

    # Ensure tables folder exists
    os.makedirs("tables", exist_ok=True)

    table_csvs = []
    for idx, table in enumerate(tables):
        df = pd.DataFrame(table[1:], columns=table[0])
        csv_name = os.path.join("tables", f"table_{idx+1}.csv")
        df.to_csv(csv_name, index=False)
        table_csvs.append({
            "table_number": idx + 1,
            "csv_file": csv_name,
            "preview_rows": df.head(3).to_dict(orient="records")
        })

    return {
        "text_data": text[:500],
        "invoice_fields": invoice_fields,
        "tables_found": len(tables),
        "table_csvs": table_csvs
    }

# ✅ DOWNLOAD SAVED CSV FILES
@app.get("/download/{filename}")
def download_csv(filename: str):
    file_path = os.path.join(os.getcwd(), "tables", filename)
    if os.path.exists(file_path) and filename.endswith(".csv"):
        return FileResponse(path=file_path, filename=filename, media_type='text/csv')
    return {"error": "File not found"}

# ✅ LIST CSV FILES
@app.get("/list_csvs/")
def list_csvs():
    files = os.listdir("tables")
    return {"csv_files": files}

# ✅ RUN ON WINDOWS
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
