# Incident: Billing API rate limit loop

Date: 2026-02-14

Agents repeatedly retried billing API calls immediately after HTTP 429 responses. The retry loop extended the outage because each retry reset the account-level rate window.

Correction: For HTTP 429, wait 90 seconds before the first retry, then use exponential backoff capped at 5 minutes. Include the account ID and retry count in logs.
