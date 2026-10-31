ObjC.import('CoreGraphics');
// Wait for the triggering modifiers to be released before sending Cmd+Space.
const modifiers = (1 << 17) | (1 << 18) | (1 << 19) | (1 << 20);
const deadline = Date.now() + 5000;
while (($.CGEventSourceFlagsState(0) & modifiers) !== 0) {
    if (Date.now() >= deadline) throw new Error('Spotlight: modifiers still held');
    delay(0.02);
}
Application('System Events').keyCode(49, {using: ['command down']});
