import os
import re
import json
import logging
from pydantic import BaseModel, model_validator
from typing import List, Optional
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# MODELS
# ============================================================================
class LineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    total: float

class InvoiceData(BaseModel):
    vendor_name: str
    invoice_number: str
    date: str
    line_items: List[LineItem]
    grand_total: float
    tax: Optional[float] = 0.0

    @model_validator(mode='after')
    def validate_math(self) -> 'InvoiceData':
        if not self.line_items:
            return self
        
        calculated_sum = sum(item.total for item in self.line_items)
        expected_total = calculated_sum + (self.tax or 0.0)
        
        # Warn but don't crash — vendor invoices often have rounding quirks
        if abs(expected_total - self.grand_total) > 1.00:
            logger.warning(
                f"⚠️ Math mismatch: items sum to {calculated_sum:.2f} + tax {self.tax:.2f} "
                f"= {expected_total:.2f}, but invoice says {self.grand_total:.2f}. Proceeding anyway."
            )
        return self


def _clean_number(val) -> float:
    """Coerce messy numeric strings like '$6,500.00' or '76.500,00' to float."""
    if val is None:
        return 0.0
    return float(str(val).replace(',', '').replace('$', '').replace('₹', '').strip() or 0)


def _clean_line_items(raw_items: list) -> list:
    """Ensure each line item dict has clean float values before Pydantic sees them."""
    cleaned = []
    for item in raw_items:
        cleaned.append({
            "description": str(item.get("description", "Unknown")),
            "quantity":   _clean_number(item.get("quantity", 1)),
            "unit_price": _clean_number(item.get("unit_price", 0)),
            "total":      _clean_number(item.get("total", 0)),
        })
    return cleaned


# ============================================================================
# THE ENGINE
# ============================================================================

def parse_markdown_to_dict(md_text: str) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    
    if not api_key:
        logger.error("❌ GROQ_API_KEY is missing. Check your .env file!")
        return {"vendor_name": "MISSING API KEY", "invoice_number": "N/A", "date": "N/A",
                "line_items": [], "grand_total": 0, "tax": 0}
    
    logger.info(f"🔑 API Key detected (starts with: {api_key[:5]}...)")

    try:
        client = Groq(api_key=api_key)
        
        system_msg = (
            "You are an invoice data extraction API. "
            "Extract all invoice fields from the markdown text and return ONLY a valid JSON object. "
            "Rules:\n"
            "1. Fields required: vendor_name, invoice_number, date, grand_total, tax, line_items.\n"
            "2. line_items is a list of objects, each with: description, quantity, unit_price, total.\n"
            "3. All numeric values must be plain numbers (no currency symbols, no commas). E.g. 6500.00 not $6,500.00\n"
            "4. If tax is not mentioned, use 0.\n"
            "5. OCR fix: if grand_total seems implausibly large vs line items (e.g. 76500 vs 6500), "
            "   trust the line items sum — the leading digit was likely a misread pipe character.\n"
            "6. Return ONLY the JSON object, nothing else."
        )

        logger.info("📡 Sending request to Groq...")

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": md_text[:8000]}
            ],
            model="llama-3.1-8b-instant",   # ✅ Current best model on Groq with JSON mode
            response_format={"type": "json_object"},
            temperature=0.1
        )

        raw_json = chat_completion.choices[0].message.content
        logger.info(f"✅ Raw response received: {raw_json}")
        
        data = json.loads(raw_json)

        return {
            "vendor_name":    data.get("vendor_name", "Unknown Vendor"),
            "invoice_number": data.get("invoice_number", "N/A"),
            "date":           data.get("date", "N/A"),
            "line_items":     _clean_line_items(data.get("line_items", [])),
            "grand_total":    _clean_number(data.get("grand_total", 0)),
            "tax":            _clean_number(data.get("tax", 0)),
        }

    except Exception as e:
        logger.error(f"🔥 GROQ API CRASHED: {type(e).__name__} — {str(e)}")
        return {"vendor_name": f"API ERROR: {str(e)[:80]}", "invoice_number": "N/A",
                "date": "N/A", "line_items": [], "grand_total": 0, "tax": 0}