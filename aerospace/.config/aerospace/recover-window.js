// Super+O: choose an on-screen window using macOS accessibility, including
// dialogs AeroSpace excludes. Covered windows count as on-screen; minimized
// windows and windows parked off-screen on other workspaces do not.
// Run with --list to inspect candidates, or --raise <CGWindowID> to recover
// one directly. No window titles are read through Screen Recording APIs.
ObjC.import('Cocoa');
ObjC.import('CoreGraphics');

function run(args) {
    const system = Application('System Events');
    const app = Application.currentApplication();
    app.includeStandardAdditions = true;
    const screens = $.NSScreen.screens;
    const desktopTop = screens.objectAtIndex(0).frame.size.height;
    const displays = [];
    for (let i = 0; i < screens.count; i++) {
        const frame = screens.objectAtIndex(i).frame;
        displays.push({x: frame.origin.x,
            y: desktopTop - frame.origin.y - frame.size.height,
            width: frame.size.width, height: frame.size.height});
    }

    const windows = ObjC.deepUnwrap(ObjC.castRefToObject(
        $.CGWindowListCopyWindowInfo(17, 0))); // on-screen, excluding desktop
    const candidates = [];
    const processes = {};
    for (const info of windows) {
        if (info.kCGWindowLayer !== 0) continue;
        if (info.kCGWindowOwnerName === 'osascript') continue;
        const bounds = info.kCGWindowBounds;
        const cx = bounds.X + bounds.Width / 2;
        const cy = bounds.Y + bounds.Height / 2;
        if (!displays.some(d => cx >= d.x && cx < d.x + d.width &&
            cy >= d.y && cy < d.y + d.height)) continue;
        const pid = info.kCGWindowOwnerPID;
        // Border overlays also have CG windows, but no corresponding AX window.
        try {
            if (!processes[pid]) {
                const process = system.processes.whose({unixId: pid})()[0];
                if (!process) continue;
                processes[pid] = {process: process, name: process.name(),
                    windows: process.windows()};
            }
            const entry = processes[pid];
            for (const window of entry.windows) {
                const pos = window.position();
                const size = window.size();
                if (Math.abs(pos[0] - bounds.X) > 2 ||
                    Math.abs(pos[1] - bounds.Y) > 2 ||
                    Math.abs(size[0] - bounds.Width) > 2 ||
                    Math.abs(size[1] - bounds.Height) > 2) continue;
                const title = window.name() || 'Untitled window';
                candidates.push({id: info.kCGWindowNumber, window: window,
                    process: entry.process,
                    label: entry.name + ' — ' + title + ' [' + info.kCGWindowNumber + ']'});
                break;
            }
        } catch (_) {
            // An app can exit, or a transient window can disappear, during enumeration.
        }
    }

    if (args[0] === '--list') {
        return candidates.map(c => c.label).join('\n');
    }
    let target;
    if (args[0] === '--raise') {
        target = candidates.find(c => String(c.id) === args[1]);
        if (!target) throw new Error('Window is no longer available on the current screens.');
    } else {
        if (!candidates.length) {
            app.displayAlert('No windows available to recover', {
                message: 'If windows are visible, check Accessibility permission for AeroSpace in System Settings.'});
            return;
        }
        app.activate();
        const selected = app.chooseFromList(candidates.map(c => c.label), {
            withTitle: 'Recover a window',
            withPrompt: 'Bring a covered window or dialog to the front:',
            okButtonName: 'Bring Forward', multipleSelectionsAllowed: false,
            emptySelectionAllowed: false});
        if (selected === false) return;
        target = candidates.find(c => c.label === selected[0]);
    }

    try {
        target.process.frontmost = true;
        target.window.actions.byName('AXRaise').perform();
        delay(0.15);
        const pos = target.window.position();
        const size = target.window.size();
        // AX positions already use CoreGraphics coordinates, including on
        // secondary monitors. Warp without sending a mouse click.
        $.CGWarpMouseCursorPosition($.CGPointMake(
            pos[0] + size[0] / 2, pos[1] + size[1] / 2));
    } catch (error) {
        throw new Error('Could not recover the selected window: ' + error.message);
    }
}
