# 01: Spike — can pane metadata carry mute?

Status: ready-for-agent
Type: research
Blocked by: none

Time limit: half a day. The result is an answer under `## Answer`, not production code.

**Question:** Can a `report-metadata` token on a pane serve as the pane mute flag that the client checks before it plays a sound?

Answer each point with evidence from the Herdr 0.9.5 source and from a test against an isolated Herdr server (never the user's live server):

- [ ] The exact command that sets and clears the token, and what `--source`, `--applies-to-source`, `--seq`, and `--ttl-ms` require.
- [ ] A uniquely prefixed token name (proposal: `dotfiles_pane_mute`) is valid under Herdr's token key rules. Tokens share one flat map by name, so search the Herdr source and the agent integrations in this repo for writers of the same name.
- [ ] Without `--ttl-ms`, the token stays until it is cleared.
- [ ] The token is in effect on the server when the command returns.
- [ ] Attached clients receive the token in their pane state. If they do not, a client can read it through the existing API at sound time.
- [ ] Delivery order: after the mute command returns, can a notification for that pane reach the client sound decision before the snapshot with the new token? Answer from the source and with a test on an isolated server. If yes, the client must query the pane through the existing API at sound time; record that for ticket 02.
- [ ] The token survives client detach and reopen, stays on the pane after move and rename, and goes away on pane close and on full server restart, including restored panes.
- [ ] `herdr pane get` / `pane list` show the token.
- [ ] Where the client decides to play completion and needs-input sounds, and how small the patch at that point would be.

**Outcome:** If every point passes, update ticket 02 with the exact command and patch location and set it to `ready-for-agent`. If a point fails, stop and report to the user with the failed point and the options. Do not fall back to a client-local store without a user decision.
