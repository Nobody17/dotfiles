# Incident: Auth refresh wrote world-readable token

Date: 2026-03-03

A generated helper wrote `.billing-token` with default file permissions. Production rejected the token because the file mode was 0644.

Correction: Any token refresh workflow must set token files to mode 0600 and verify permissions before calling the billing API.
