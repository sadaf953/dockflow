from pydantic import BaseModel, Field, model_validator
from typing import List

class LineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    total: float

class InvoiceData(BaseModel):
    vendor_name: str
    invoice_number: str
    date: str
    account_details: str
    line_items: List[LineItem]
    grand_total: float

    @model_validator(mode='after')
    def validate_invoice_math(self) -> 'InvoiceData':
        # Rule: Sum of line items must equal grand total
        calculated_sum = sum(item.total for item in self.line_items)
        if abs(calculated_sum - self.grand_total) > 0.05: # 5 cent margin for rounding
            raise ValueError(f"Math Check Failed: Items sum to {calculated_sum}, but Total is {self.grand_total}")
        return self
