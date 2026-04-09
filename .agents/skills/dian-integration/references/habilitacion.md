# Habilitacion

Use habilitacion when validating DIAN connectivity and test-set compliance before production.

Required runtime inputs:

- `DIAN_ENVIRONMENT=habilitacion`
- `DIAN_SOFTWARE_ID`
- `DIAN_SOFTWARE_PIN`
- `DIAN_TEST_SET_ID`
- certificate path and password

Recommended sequence:

1. Verify the certificate loads locally.
2. Submit a known-good invoice payload.
3. Save the returned `tracking_id`.
4. Query `GET /api/v1/documents/submissions/{tracking_id}` until DIAN returns a functional result.
5. Only after repeated success, move to production credentials and production endpoint configuration.
