// Print one line per on-screen-capable window:
//
//     <window-id> <process-id> <x> <y> <width> <height> <is-on-screen>
//
// AeroSpace uses the CGWindowID as its window id, so the first column joins
// directly with "aerospace list-windows --format '%{window-id}'".
//
// The members of a macOS native tab group are separate windows that share
// one frame, and only the active tab is on screen. float-macos-tabs.sh uses
// exactly that to keep the hidden tabs out of the tiling tree.
//
// Only the window number, the owner and the frame are read, so this needs
// no Screen Recording permission. A window title would need it.
import CoreGraphics
import Foundation

let options: CGWindowListOption = [.optionAll, .excludeDesktopElements]
guard let windows = CGWindowListCopyWindowInfo(options, kCGNullWindowID) as? [[String: Any]] else {
    exit(1)
}

for window in windows {
    // Layer 0 is the normal window layer. Menus, tooltips and the shadow
    // helpers of a border program sit on other layers.
    guard let layer = window[kCGWindowLayer as String] as? Int, layer == 0 else { continue }
    guard let windowIdentifier = window[kCGWindowNumber as String] as? Int else { continue }
    guard let processIdentifier = window[kCGWindowOwnerPID as String] as? Int else { continue }
    guard let boundsDictionary = window[kCGWindowBounds as String] as? [String: Any],
          let bounds = CGRect(dictionaryRepresentation: boundsDictionary as CFDictionary)
    else { continue }

    let isOnScreen = (window[kCGWindowIsOnscreen as String] as? Bool ?? false) ? 1 : 0
    print("\(windowIdentifier) \(processIdentifier)"
        + " \(Int(bounds.origin.x)) \(Int(bounds.origin.y))"
        + " \(Int(bounds.width)) \(Int(bounds.height)) \(isOnScreen)")
}
