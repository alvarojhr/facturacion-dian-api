# Examples

## Invoice

Use a structure like:

```json
{
  "document": {
    "number": "FDK000001",
    "type": "FACTURA_ELECTRONICA",
    "issue_date": "2026-03-12",
    "issue_time": "14:30:00-05:00",
    "payment_method": "CASH"
  },
  "buyer": {
    "document_number": "800199436",
    "document_type": "NIT",
    "name": "Empresa Ejemplo S.A.S."
  },
  "resolution": {
    "number": "18764000001",
    "prefix": "FDK"
  },
  "totals": {
    "subtotal": 100000,
    "tax_total": 19000,
    "total": 119000
  },
  "line_items": [
    {
      "description": "Tornillo hexagonal 1/4 x 1 zinc",
      "quantity": 100,
      "unit_price": 500,
      "line_total": 50000,
      "tax_type": "IVA_19",
      "tax_amount": 9500
    }
  ],
  "submission_options": {
    "software_id": "software-123",
    "software_pin": "12345",
    "technical_key": "fc8eac422eba16e22ffd8c6f94b3f40a6e38162c",
    "test_set_id": "test-set-123"
  }
}
```

## Credit note

- Set `document.type` to `NOTA_CREDITO`
- Put the note number in `document.number`
- Put the referenced invoice metadata in `references`
- Put the functional explanation in `references.reason`

## Mapping hint

When adapting an ERP payload:

- invoice header fields usually map into `document`, `resolution`, and `totals`
- customer master data maps into `buyer`
- runtime DIAN credentials belong in `submission_options`, not in business data
