// Native equivalent of send-herdr-focus.js: avoid starting JavaScript on every
// key repeat. Build as aerospace-send-herdr-focus (see !install/install.fish).
import AppKit

func code(_ value: String) -> FourCharCode {
    value.utf8.reduce(0) { ($0 << 8) | UInt32($1) }
}

func property(_ name: String, in container: NSAppleEventDescriptor = .null()) -> NSAppleEventDescriptor {
    let record = NSAppleEventDescriptor.record()
    record.setDescriptor(NSAppleEventDescriptor(typeCode: code("prop")), forKeyword: code("want"))
    record.setDescriptor(NSAppleEventDescriptor(enumCode: code("prop")), forKeyword: code("form"))
    record.setDescriptor(NSAppleEventDescriptor(typeCode: code(name)), forKeyword: code("seld"))
    record.setDescriptor(container, forKeyword: code("from"))
    return record.coerce(toDescriptorType: code("obj "))!
}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

let args = CommandLine.arguments
let keys = ["left": 57376, "down": 57377, "up": 57378, "right": 57379]
guard args.count == 3, let pid = Int32(args[1]), pid > 0, let key = keys[args[2]] else {
    fail("Usage: aerospace-send-herdr-focus PID left|down|up|right")
}
guard let front = NSWorkspace.shared.frontmostApplication,
      front.processIdentifier == pid, front.bundleIdentifier == "com.mitchellh.ghostty" else {
    fail("Focused Ghostty process changed")
}

// Address the PID, not the app name: multiple Ghostty instances can be open.
// Resolve the selected terminal inside that process; never synthesize key
// events, which would disturb the user's held modifiers.
let event = NSAppleEventDescriptor(eventClass: code("Ghst"), eventID: code("PfAc"),
                                   targetDescriptor: NSAppleEventDescriptor(processIdentifier: pid),
                                   returnID: -1, transactionID: 0)
event.setParam(NSAppleEventDescriptor(string: "text:\\x1b[\(key)u"), forKeyword: code("----"))
event.setParam(property("GTfT", in: property("GWsT", in: property("GFWn"))), forKeyword: code("GonT"))
do {
    let reply = try event.sendEvent(options: .waitForReply, timeout: 3)
    if let error = reply.paramDescriptor(forKeyword: code("errn")), error.int32Value != 0 {
        fail("Ghostty AppleEvent failed: \(error.int32Value)")
    }
    guard reply.paramDescriptor(forKeyword: code("----"))?.booleanValue == true else {
        fail("Ghostty rejected terminal input")
    }
} catch {
    fail("Ghostty input failed: \(error.localizedDescription)")
}
