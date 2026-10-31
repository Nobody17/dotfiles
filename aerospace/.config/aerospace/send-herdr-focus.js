// Send a Kitty-protocol F13-F16 sequence directly to the focused Ghostty surface.
// Application(pid) and saved System Events process references can resolve by
// application name, targeting the wrong instance. Use a PID AppleEvent address.
ObjC.import('AppKit');

function code(value) {
    return value.split('').reduce((result, char) => result * 256 + char.charCodeAt(0), 0);
}

// Property object specifiers from Ghostty.sdef: front window -> selected tab ->
// focused terminal. The container chain is evaluated by the addressed process.
function property(name, container) {
    const record = $.NSAppleEventDescriptor.recordDescriptor;
    record.setDescriptorForKeyword($.NSAppleEventDescriptor.descriptorWithTypeCode(code('prop')), code('want'));
    record.setDescriptorForKeyword($.NSAppleEventDescriptor.descriptorWithEnumCode(code('prop')), code('form'));
    record.setDescriptorForKeyword($.NSAppleEventDescriptor.descriptorWithTypeCode(code(name)), code('seld'));
    record.setDescriptorForKeyword(container || $.NSAppleEventDescriptor.nullDescriptor, code('from'));
    return record.coerceToDescriptorType(code('obj '));
}

function run(argv) {
    const pid = Number(argv[0]);
    const key = {left: 57376, down: 57377, up: 57378, right: 57379}[argv[1]];
    if (!Number.isInteger(pid) || pid <= 0 || !key) throw Error('Invalid focus target or direction');
    const front = $.NSWorkspace.sharedWorkspace.frontmostApplication;
    if (front.processIdentifier !== pid || ObjC.unwrap(front.bundleIdentifier) !== 'com.mitchellh.ghostty') {
        throw Error('Focused Ghostty process changed');
    }

    const target = $.NSAppleEventDescriptor.descriptorWithProcessIdentifier(pid);
    const event = $.NSAppleEventDescriptor.appleEventWithEventClassEventIDTargetDescriptorReturnIDTransactionID(
        code('Ghst'), code('PfAc'), target, -1, 0);
    event.setParamDescriptorForKeyword(
        $.NSAppleEventDescriptor.descriptorWithString('text:\\x1b[' + key + 'u'), code('----'));
    event.setParamDescriptorForKeyword(property('GTfT', property('GWsT', property('GFWn'))), code('GonT'));
    const error = Ref();
    const reply = event.sendEventWithOptionsTimeoutError(3, 3, error);
    if (reply.descriptorType === undefined) throw Error('Ghostty input failed: ' + ObjC.unwrap(error[0].localizedDescription));
    const failure = reply.paramDescriptorForKeyword(code('errn')).int32Value;
    if (failure !== undefined && failure !== 0) throw Error('Ghostty AppleEvent failed: ' + failure);
    const result = reply.paramDescriptorForKeyword(code('----'));
    if (!result || !result.booleanValue) throw Error('Ghostty rejected terminal input');
}
