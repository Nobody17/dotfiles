# Local Herdr customization

Language for the privately maintained Herdr changes distributed through these dotfiles.

## Language

**Local patch**:
The privately maintained changes added to an upstream Herdr release for personal use.
_Avoid_: Upstream feature

**Patched release**:
A particular upstream Herdr release with the local patch applied and verified.
_Avoid_: Latest build

**Pane mute**:
A flag on a server pane that makes patched clients skip its Herdr completion and needs-input sounds while preserving terminal bells, toasts, and visible agent status. It is stored as pane metadata, applies to every patched client viewing that server, survives client detach, and resets after the server restarts.
_Avoid_: Hide agent, disable notifications

**Worker pane**:
A pane containing an agent whose work is directed by a parent agent rather than directly by the user.
_Avoid_: Background tab

**Server session**:
One uninterrupted run of a Herdr server, during which clients can detach and reconnect without ending the session.
_Avoid_: Client window
