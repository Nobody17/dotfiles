// AeroSpace can focus an empty workspace while macOS keeps delivering input
// to the previous app. Give native focus to SystemUIServer (no window to raise).
// The Dock prevents Spotlight's Cmd+Space shortcut from opening its panel.
ObjC.import('AppKit');

function run(argv) {
    if (!argv[0]) return;
    const shell = Application.currentApplication();
    shell.includeStandardAdditions = true;
    const aerospace = "'" + argv[0].replace(/'/g, "'\\''") + "'";
    const previous = $.NSWorkspace.sharedWorkspace.frontmostApplication;
    try {
        // Query live state, not callback environment: callbacks can arrive late.
        const count = shell.doShellScript(aerospace +
            ' list-windows --workspace focused --count').trim();
        if (count !== '0') return;
    } catch (_) {
        return; // A disconnected server does not mean an empty workspace.
    }
    if ($.NSWorkspace.sharedWorkspace.frontmostApplication.processIdentifier !==
        previous.processIdentifier) return;
    const menuServices = $.NSRunningApplication.runningApplicationsWithBundleIdentifier('com.apple.systemuiserver');
    if (menuServices.count > 0) menuServices.objectAtIndex(0).activateWithOptions(2);
}
