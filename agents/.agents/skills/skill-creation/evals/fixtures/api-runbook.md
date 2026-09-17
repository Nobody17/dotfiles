# Billing API Runbook

## Scope

Agents use this runbook when diagnosing billing API incidents or writing automation around the billing API.

## Endpoint examples

Check account status:

```bash
curl -sS -H "Authorization: Bearer $BILLING_TOKEN" \
  "https://billing.example.test/v1/accounts/$ACCOUNT_ID/status" | jq .
```

Refresh an auth token:

```bash
scripts/refresh-token.sh --service billing --output .billing-token
```

## Common failures

- HTTP 429 means the account-level rate limit was exceeded. Wait 90 seconds and retry with exponential backoff capped at 5 minutes.
- HTTP 401 after token refresh usually means the token file was written with mode 0644. Rewrite it with mode 0600.

## Validation

After any billing API change, run:

```bash
scripts/validate-billing-workflow.sh --account "$ACCOUNT_ID" --dry-run
```

The workflow is not complete until validation exits 0.
