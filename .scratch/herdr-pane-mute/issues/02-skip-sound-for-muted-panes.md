# 02: Skip Herdr sounds for muted panes

Status: needs-info
Blocked by: 01

**What to build:** A local client patch that skips automatic completion and needs-input sounds for panes that carry the mute token from ticket 01. Store it in `mise/.config/mise/herdr-local/` so it builds in an isolated source checkout. Automatic installation is ticket 04.

Set to `ready-for-agent` when ticket 01 records the mute command and the patch location.

- [ ] A pane with the mute token plays neither completion nor needs-input sound. A pane without it, including one with the same agent type, keeps its existing behavior.
- [ ] Unmute (clearing the token) restores the existing policy and does not override a global or agent-type sound disable.
- [ ] Toasts, notification navigation, agent status, wait behavior, and terminal bells do not change. A muted pane is not marked seen or complete.
- [ ] A notification right after a successful mute command is silent. The test order depends on the delivery-order answer of ticket 01:
  - If a notification can arrive before the snapshot with the token: the server has the token, the client snapshot stays unmuted, the notification arrives, the API lookup returns the token, and no sound plays. A patch that reads only the snapshot must fail this test.
  - If Herdr always delivers the snapshot first: the test starts unmuted, delivers the snapshot with the token through the same path Herdr uses, then delivers the notification. Ticket 01 records the source evidence for this order.
- [ ] The patch touches only the sound decision and, if needed, the token lookup. No new CLI commands, no rendering changes, no server or wire changes.
- [ ] The behavioral tests can run on their own (one documented command), because ticket 04 runs them during each install.
- [ ] Tests at the existing client notification-policy boundary cover the cases above with deterministic notification inputs. No real models, no audible speakers.
- [ ] Relevant upstream checks and compatibility fixtures pass without changed protocol expectations.
