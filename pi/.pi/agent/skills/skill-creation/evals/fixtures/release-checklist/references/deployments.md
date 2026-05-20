# Deployment Reference

Production deploys use the same script as staging with a different environment argument.

Rollback verification is mandatory after any release that touches payments, auth, or database migrations. Agents often skip this because the old checklist only mentions successful deploys.

Verification command:

```bash
scripts/verify-rollback.sh --env production --release "$RELEASE_ID"
```

If verification fails, do not announce the release as complete. Escalate to the release owner and include the verification error.
