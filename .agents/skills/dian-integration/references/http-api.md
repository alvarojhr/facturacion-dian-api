# HTTP API

Base endpoints:

- `POST /api/v1/documents/submissions`
- `GET /api/v1/documents/submissions/{tracking_id}`
- `POST /api/v1/attached-documents`
- `POST /api/v1/customers/lookup`
- `POST /api/v1/numbering-ranges/lookup`

Submission request structure:

- `document`: number, type, issue date/time, payment method, optional POS data
- `issuer`: optional issuer overrides such as NIT, DV, software owner NIT
- `buyer`: buyer identity and contact data
- `resolution`: authorized resolution number and prefix, optional range metadata
- `totals`: subtotal, tax total, total
- `line_items`: commercial lines with DIAN tax classification
- `references`: referenced document metadata for note documents
- `submission_options`: runtime-only DIAN parameters like software id/pin, technical key, test set id, and whether to return XML artifacts
- `client_reference`: opaque caller correlation id

Submission response structure:

- `submission_id`
- `tracking_id`
- `client_reference`
- `document_key`
- `qr_url`
- `status`
- `messages`
- `dian_response`
- `artifacts`
