import os
import shutil
import tempfile
import traceback
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from app.sheets_sync import sync_to_payments_sheet

# 1. Import your working converter
from app.converter import process_pdf_to_markdown

# 2. Import the Logic from invoice_parser.py
# Make sure your invoice_parser.py has 'parse_markdown_to_dict' and 'InvoiceData'
from app.invoice_parser import parse_markdown_to_dict, InvoiceData

load_dotenv()

app = FastAPI(title=os.getenv("APP_NAME", "PDF to MD Converter"))

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Invoice Parser Pro (Zero-AI)</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; background: #f4f7f6; }
            .card { background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h2 { color: #333; margin-top: 0; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
            textarea { width: 100%; height: 400px; font-family: monospace; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            button { padding: 12px 24px; font-size: 16px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 5px; transition: 0.3s; }
            button:hover { background: #0056b3; }
            button:disabled { background: #ccc; }
            .copy-btn { background: #28a745; margin-top: 10px; width: 100%; }
            .status { margin-top: 15px; font-weight: bold; padding: 10px; border-radius: 4px; display: none; }
            .success { background: #d4edda; color: #155724; display: block; }
            .error { background: #f8d7da; color: #721c24; display: block; }
            label { font-weight: bold; display: block; margin-bottom: 5px; color: #666; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>📄 Invoice to Data (Zero-Trace)</h2>
            <p>Upload a PDF to extract Markdown and Validated Accounting Data.</p>
            
            <input type="file" id="pdfFile" accept=".pdf">
            <button onclick="convertPDF()" id="convertBtn">Process Invoice</button>
            
            <div id="statusBox" class="status"></div>

            <div class="grid">
                <div>
                    <label>Raw Markdown Output</label>
                    <textarea id="outputMd" placeholder="Markdown will appear here..."></textarea>
                    <button class="copy-btn" onclick="copyText('outputMd')">📋 Copy Markdown</button>
                </div>
                <div>
                    <label>Validated Accounting JSON</label>
                    <textarea id="outputJson" placeholder="Structured data will appear here..."></textarea>
                    <button class="copy-btn" style="background:#6c757d" onclick="copyText('outputJson')">📋 Copy JSON</button>
                </div>
            </div>
        </div>

        <script>
            async function convertPDF() {
                const fileInput = document.getElementById('pdfFile');
                const outputMd = document.getElementById('outputMd');
                const outputJson = document.getElementById('outputJson');
                const btn = document.getElementById('convertBtn');
                const statusBox = document.getElementById('statusBox');

                if (!fileInput.files[0]) {
                    alert("Please select a PDF first.");
                    return;
                }

                btn.innerText = "🔍 Parsing & Validating Math...";
                btn.disabled = true;
                statusBox.className = "status";
                statusBox.innerText = "";

                const formData = new FormData();
                formData.append("file", fileInput.files[0]);

                try {
                    const response = await fetch('/convert/', { method: 'POST', body: formData });
                    const data = await response.json();
                    
                    if (response.ok) {
                        outputMd.value = data.markdown;
                        outputJson.value = JSON.stringify(data.structured_data, null, 4);
                        statusBox.innerText = "✅ Success: Math Validation Passed! Invoice saved to Google Sheets.";
                        statusBox.className = "status success";
                    } else {
                        statusBox.innerText = "❌ Error: " + data.detail;
                        statusBox.className = "status error";
                        outputMd.value = data.markdown || "";
                    }
                } catch (error) {
                    statusBox.innerText = "❌ Failed to connect to server.";
                    statusBox.className = "status error";
                }

                btn.innerText = "Process Invoice";
                btn.disabled = false;
            }

            function copyText(id) {
                const output = document.getElementById(id);
                output.select();
                document.execCommand('copy');
                alert("Copied to clipboard!");
            }
        </script>
    </body>
    </html>
    """

@app.post("/convert/")
async def convert_pdf(file: UploadFile = File(...)):
    # 1. Basic File Check
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    file_base_name = file.filename.rsplit(".", 1)[0]

    # 2. Start Zero-Trace Processing
    with tempfile.TemporaryDirectory() as temp_dir:
        pdf_path = os.path.join(temp_dir, file.filename)
        
        # Save file to temp location
        with open(pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        try:
            # STEP 1: Convert PDF to Markdown (using your converter.py)
            md_text = process_pdf_to_markdown(pdf_path, temp_dir, file_base_name)
            
            # STEP 2: Extract Data via Regex (using invoice_parser.py)
            raw_dict = parse_markdown_to_dict(md_text)
            
            # STEP 3: Validate Math (using invoice_parser.py Pydantic Model)
            # This line will trigger the 'validate_math' check.
            # If math is wrong, it raises a ValueError.
            validated_invoice = InvoiceData(**raw_dict)
            sync_to_payments_sheet(validated_invoice)

            
            # STEP 4: Success - Return both MD and Structured Data
            return {
                "message": "Validation Passed",
                "markdown": md_text,
                "structured_data": validated_invoice.dict()
            }
            
        except ValueError as ve:
            # This catches Pydantic Math errors and shows them in the UI
            raise HTTPException(status_code=422, detail=str(ve))
            
        except Exception as e:
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Processing Error: {str(e)}")

# Note: Google Sheets sync is currently paused until we confirm extraction accuracy.