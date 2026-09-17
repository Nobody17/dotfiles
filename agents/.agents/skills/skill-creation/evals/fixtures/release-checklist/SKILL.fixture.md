---
name: release-checklist
description: Helps with releases.
---

# Release Checklist

Use this checklist when preparing a service release.

## Workflow

1. Confirm the release branch is green in CI.
2. Deploy to staging with `scripts/deploy.sh staging`.
3. Smoke test the staging URL.
4. Deploy to production with `scripts/deploy.sh production`.
5. Announce the release in Slack.

## References

- Read [deployments](references/deployments.md) for deployment command details.
