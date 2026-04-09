# Troubleshooting

## 422

The request shape does not satisfy the public API schema. Check missing blocks or wrong field names.

## 503

Local configuration is incomplete or invalid. Typical causes:

- missing certificate file
- wrong certificate password
- missing `DIAN_SOFTWARE_ID`
- missing `DIAN_SOFTWARE_PIN`
- missing `DIAN_TECHNICAL_KEY` for invoices
- missing `DIAN_TEST_SET_ID` in habilitacion

## 502

DIAN returned a non-success HTTP response or the transport failed before a functional response was parsed.

## 504

DIAN timed out. Treat this as upstream unavailability, not a business rejection.

## Rejected submission with HTTP 200

This means DIAN processed the request and rejected it functionally. Inspect:

- `messages`
- `dian_response.status_code`
- `dian_response.status_description`
- `dian_response.error_messages`
