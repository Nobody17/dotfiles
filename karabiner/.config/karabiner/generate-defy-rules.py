#!/usr/bin/env python3
"""Regenerate the Dygma Defy rules in ~/.config/karabiner/karabiner.json.
Edit the tables below and re-run:  python3 ~/.config/karabiner/generate-defy-rules.py
Karabiner watches the file and reloads within a second; no restart needed.
"""
import json, os, copy

HOME = os.path.expanduser("~")
DEFY = {"type": "device_if", "identifiers": [{"vendor_id": 13807, "product_id": 18}]}
MOUSE = {"type": "device_if", "identifiers": [
    {"vendor_id": 1149, "product_id": 32792},
    {"vendor_id": 1149, "product_id": 32793},  # ExpertBT5.0 over Bluetooth
]}
BUILTIN = {"type": "device_if", "identifiers": [{"is_built_in_keyboard": True}]}
KEYCHRON = {"type": "device_if", "identifiers": [
    {"vendor_id": 1452, "product_id": 592},  # Keychron K8 wired, Mac mode
    {"vendor_id": 13364, "product_id": 53288},  # Keychron Ultra-Link 8K receiver
]}

# Karabiner ignores pointing devices by DEFAULT. Both of these must opt in explicitly:
# the Defy because it also presents a mouse interface, the trackball to see buttons 4/5.
DEVICES = [
    {"identifiers": {"is_keyboard": True, "is_pointing_device": True,
                     "vendor_id": 13807, "product_id": 18},
     "ignore": False, "manipulate_caps_lock_led": True,
     "disable_built_in_keyboard_if_exists": False},
    {"identifiers": {"is_pointing_device": True, "vendor_id": 1149, "product_id": 32792},
     "ignore": False},
    {"identifiers": {"is_pointing_device": True, "vendor_id": 1149, "product_id": 32793},
     "ignore": False},
]
TERMS = ["^com\\.apple\\.Terminal$", "^com\\.googlecode\\.iterm2$", "^com\\.mitchellh\\.ghostty$",
         "^com\\.github\\.wez\\.wezterm$", "^net\\.kovidgoyal\\.kitty$", "^org\\.alacritty$",
         "^dev\\.warp\\.Warp-Stable$", "^co\\.zeit\\.hyper$"]
IN_TERM  = {"type": "frontmost_application_if", "bundle_identifiers": TERMS}
NOT_TERM = {"type": "frontmost_application_unless", "bundle_identifiers": TERMS}
# Reuse the right Option the user is ALREADY holding (AltGr) instead of synthesizing a
# left Option press. The German layout only needs the generic Option bit, which a real
# right-Option press sets - and this avoids emitting Option taps that global "double-tap
# Option" hotkeys (e.g. Claude Desktop Quick Entry) pick up.
OPT, OPTSHIFT, CMD = ["right_option"], ["right_option", "left_shift"], ["left_command"]
CMDSHIFT = ["left_command", "left_shift"]

# --- Linux German AltGr layer -> macOS German combo producing the same character ---
ALTGR = [
    ("q",                "@",  [{"key_code": "l", "modifiers": OPT}]),
    ("7",                "{",  [{"key_code": "8", "modifiers": OPT}]),
    ("8",                "[",  [{"key_code": "5", "modifiers": OPT}]),
    ("9",                "]",  [{"key_code": "6", "modifiers": OPT}]),
    ("0",                "}",  [{"key_code": "9", "modifiers": OPT}]),
    ("hyphen",           "\\", [{"key_code": "7", "modifiers": OPTSHIFT}]),
    ("non_us_backslash", "|",  [{"key_code": "7", "modifiers": OPT}]),
    # macOS German ~ is a DEAD key (option+n); the trailing space commits it
    ("close_bracket",    "~",  [{"key_code": "n", "modifiers": OPT},
                                {"key_code": "spacebar"}]),
]

# --- macOS German swaps these two physical keys vs Linux German: send the other one ---
KEYSWAP = [("grave_accent_and_tilde", "non_us_backslash"),   # left of 1 -> ^ / degree
           ("non_us_backslash", "grave_accent_and_tilde")]   # left of Y -> < / >

# --- Terminal Meta layer: left Option = Alt/Meta (ESC prefix), like Linux.
#     Right Option stays AltGr for symbols above. ---
META_KEYS = ([chr(c) for c in range(ord("a"), ord("z") + 1)]
             + [str(d) for d in range(10)]
             + ["delete_or_backspace", "period", "comma", "return_or_enter"])

# --- Linux terminal shortcuts (Ctrl itself is left alone so Ctrl+C stays SIGINT) ---
TERM_SHORTCUTS = [
    ("c",         ["control", "shift"], [{"key_code": "c", "modifiers": CMD}]),
    ("v",         ["control", "shift"], [{"key_code": "v", "modifiers": CMD}]),
    ("t",         ["control", "shift"], [{"key_code": "t", "modifiers": CMD}]),
    ("t",         ["control"],          [{"key_code": "t", "modifiers": CMD}]),
    ("n",         ["control", "shift"], [{"key_code": "n", "modifiers": CMD}]),
    ("w",         ["control", "shift"], [{"key_code": "w", "modifiers": CMD}]),
    ("f",         ["control", "shift"], [{"key_code": "f", "modifiers": CMD}]),
    ("page_down", ["control"], [{"key_code": "close_bracket", "modifiers": CMDSHIFT}]),
    ("page_up",   ["control"], [{"key_code": "open_bracket",  "modifiers": CMDSHIFT}]),
    # Shift+Enter is NOT remapped here. Karabiner can only send key EVENTS, and an
    # Escape key event is not the same as the ESC byte: with the Kitty keyboard
    # protocol, which Ghostty and Claude Code both use, Escape becomes "CSI 27 u".
    # Claude Code then reads Escape followed by Enter and submits the line.
    # Ghostty writes the raw two bytes instead (keybind shift+enter=text:\x1b\r in
    # ghostty/config), so the key must reach Ghostty unchanged.
]


def mod_swap(frm, to, cond=None):
    m = {"type": "basic", "from": {"key_code": frm, "modifiers": {"optional": ["any"]}},
         "to": [{"key_code": to}], "conditions": [DEFY]}
    if cond:
        m["conditions"].append(cond)
    return m


def pbtn(button, to, cond=None):
    m = {"type": "basic", "from": {"pointing_button": button, "modifiers": {"optional": ["any"]}},
         "to": to, "conditions": [MOUSE]}
    if cond:
        m["conditions"].append(cond)
    return m


def combo(key, mods, to, cond=None):
    m = {"type": "basic",
         "from": {"key_code": key, "modifiers": {"mandatory": mods, "optional": ["caps_lock"]}},
         "to": to, "conditions": [DEFY]}
    if cond:
        m["conditions"].append(cond)
    return m


# Order matters: Karabiner takes the FIRST matching manipulator. The AltGr layer must
# precede KEYSWAP, which matches non_us_backslash under any modifier state.
rules = [
    {"description": "Defy German: AltGr symbol layer at Linux positions",
     "manipulators": [combo(k, ["right_option"], to) for k, _ch, to in ALTGR]},

    {"description": "Defy German: restore Linux positions of < > and ^ degree",
     "manipulators": [mod_swap(a, b) for a, b in KEYSWAP]},

    # Super = the window manager key, like on Hyprland. AeroSpace listens to
    # Ctrl+Alt (aerospace.toml). This rule is unconditional, so the window
    # manager keys also work in terminals. Plain Option would not work there:
    # the terminal Meta layer below turns left Option into an ESC prefix.
    # This rule must precede the Control <-> Command swap, which also matches
    # left_command.
    {"description": "Defy: Super = Ctrl+Alt, the AeroSpace modifier",
     "manipulators": [
         {"type": "basic",
          "from": {"key_code": "left_command", "modifiers": {"optional": ["any"]}},
          "to": [{"key_code": "left_control", "modifiers": ["left_option"]}],
          "conditions": [DEFY]}]},

    # Super is already Ctrl+Alt from the rule above, so Super+Shift+S arrives
    # with left_control + left_option + shift.
    {"description": "Defy: Super+Shift+S opens the macOS screenshot menu",
     "manipulators": [combo("s", ["left_control", "left_option", "shift"],
                            [{"key_code": "5", "modifiers": CMDSHIFT}])]},

    # On the MacBook keyboard the same modifier sits on one key: Fn/Globe.
    # The Fn functions of the built-in keyboard are lost (emoji picker,
    # Fn+key combos). The Defy keeps its own Fn behavior.
    {"description": "MacBook built-in keyboard: Fn/Globe = Ctrl+Alt, the AeroSpace modifier",
     "manipulators": [
         {"type": "basic",
          "from": {"key_code": "fn", "modifiers": {"optional": ["any"]}},
          "to": [{"key_code": "left_control", "modifiers": ["left_option"]}],
          "conditions": [BUILTIN]}]},

    # The Defy handles its own layout in the firmware, so this stays
    # limited to the built-in keyboard.
    {"description": "MacBook built-in keyboard: Caps Lock = Escape",
     "manipulators": [
         {"type": "basic",
          "from": {"key_code": "caps_lock", "modifiers": {"optional": ["any"]}},
          "to": [{"key_code": "escape"}],
          "conditions": [BUILTIN]}]},

    {"description": "Keychron: swap Caps Lock <-> Escape",
     "manipulators": [
         {"type": "basic",
          "from": {"key_code": source, "modifiers": {"optional": ["any"]}},
          "to": [{"key_code": target}],
          "conditions": [KEYCHRON]}
         for source, target in [("caps_lock", "escape"), ("escape", "caps_lock")]]},

    {"description": "Defy: swap Control <-> Command (outside terminals)",
     "manipulators": [mod_swap(a, b, NOT_TERM) for a, b in
                      [("left_control", "left_command"), ("right_control", "right_command"),
                       ("right_command", "right_control")]]},

    {"description": "Defy in terminals: Linux shortcuts, Ctrl stays Ctrl (Ctrl+C = SIGINT)",
     "manipulators": [combo(k, mods, to, IN_TERM) for k, mods, to in TERM_SHORTCUTS]},

    {"description": "Defy in terminals: left Option = Meta/Alt (ESC prefix)",
     "manipulators": [combo(k, ["left_option"],
                            [{"key_code": "escape"}, {"key_code": k}], IN_TERM)
                      for k in META_KEYS]},

    # Defy Ctrl becomes Command outside terminals; accept both logical modifiers.
    # Mandatory modifiers are consumed so Safari receives plain Cmd+Right.
    {"description": "Kensington trackball: Ctrl/Command + buttons 4/5 = Forward in Safari",
     "manipulators": [
         {"type": "basic",
          "from": {"pointing_button": button,
                   "modifiers": {"mandatory": [modifier], "optional": ["caps_lock"]}},
          "to": [{"key_code": "right_arrow", "modifiers": ["left_command"]}],
          "conditions": [MOUSE, {"type": "frontmost_application_if",
                                 "bundle_identifiers": ["^com\\.apple\\.Safari$"]}]}
         for button in ["button4", "button5"]
         for modifier in ["control", "command"]
     ]},

    {"description": "Kensington trackball: button 5 = Back in Safari",
     "manipulators": [
         pbtn("button5", [{"key_code": "left_arrow", "modifiers": ["left_command"]}],
              {"type": "frontmost_application_if",
               "bundle_identifiers": ["^com\\.apple\\.Safari$"]}),
     ]},

    # Cmd+Left/Right rather than Cmd+[ : on the German layout "[" is Option+5, so the
    # bracket shortcut is awkward/unreliable, while Cmd+arrow is layout-independent.
    {"description": "Kensington trackball: buttons 4/5 = browser Back/Forward",
     "manipulators": [
         pbtn("button4", [{"key_code": "left_arrow",  "modifiers": ["left_command"]}]),
         pbtn("button5", [{"key_code": "right_arrow", "modifiers": ["left_command"]}]),
     ]},
]

DEFAULT_PROFILE = {
    "name": "Default profile",
    "selected": True,
    "complex_modifications": {"rules": []},
    "devices": [],
    "fn_function_keys": [],
    "simple_modifications": [],
    "virtual_hid_keyboard": {"country_code": 0, "keyboard_type_v2": "ansi"},
}

DEFAULT_CONFIGURATION = {
    "global": {"show_in_menu_bar": True},
    "profiles": [DEFAULT_PROFILE],
}


def updated_karabiner_configuration(existing_configuration, generated_rules, configured_devices):
    configuration = (
        copy.deepcopy(existing_configuration)
        if existing_configuration
        else copy.deepcopy(DEFAULT_CONFIGURATION)
    )
    profiles = configuration.setdefault("profiles", [])
    if not profiles:
        profiles.append(copy.deepcopy(DEFAULT_PROFILE))
    profiles[0]["complex_modifications"] = {"rules": copy.deepcopy(generated_rules)}
    profiles[0]["devices"] = copy.deepcopy(configured_devices)
    return configuration


def install_karabiner_rules(home_directory):
    karabiner_directory = os.path.join(home_directory, ".config", "karabiner")
    complex_modifications_directory = os.path.join(
        karabiner_directory, "assets", "complex_modifications"
    )
    os.makedirs(complex_modifications_directory, exist_ok=True)

    asset_path = os.path.join(complex_modifications_directory, "dygma-linux-parity.json")
    with open(asset_path, "w") as asset_file:
        json.dump(
            {"title": "Linux parity on macOS (Dygma Defy + built-in keyboard)", "rules": rules},
            asset_file,
            indent=2,
        )

    configuration_path = os.path.join(karabiner_directory, "karabiner.json")
    existing_configuration = None
    if os.path.exists(configuration_path):
        with open(configuration_path) as configuration_file:
            existing_configuration = json.load(configuration_file)

    configuration = updated_karabiner_configuration(existing_configuration, rules, DEVICES)
    with open(configuration_path, "w") as configuration_file:
        json.dump(configuration, configuration_file, indent=2)


if __name__ == "__main__":
    install_karabiner_rules(HOME)
    for rule in rules:
        print(f"  {len(rule['manipulators']):3}  {rule['description']}")
    print("total manipulators:", sum(len(rule["manipulators"]) for rule in rules))
