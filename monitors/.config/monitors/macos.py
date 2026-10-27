#!/opt/homebrew/bin/python3
"""Local display policy: Retina laptop scaling; maximum external resolution and refresh.

Run with --dry-run to inspect. A LaunchAgent runs this every 10 seconds.
Uses displayplacer 1.4 output and only applies changes when needed.
"""
import re
import shlex
import subprocess
import sys

DISPLAYPLACER = '/opt/homebrew/bin/displayplacer'

# These external monitors sit to the left of the MacBook.
LAPTOP_RIGHT_OF = {
    'BA6ADBB0-0DE4-4385-B2D2-2D477E83E5D0',
    'D9AD7CFD-50E6-4937-8163-3C941C9E64A5',  # Samsung
}


def displays():
    output = subprocess.check_output([DISPLAYPLACER, 'list'], text=True, timeout=8)
    result = []
    for block in output.split('Persistent screen id: ')[1:]:
        if '\nEnabled: true' not in block:
            continue
        def field(name):
            match = re.search(r'^' + re.escape(name) + r': (.+)$', block, re.M)
            if match is None:
                raise ValueError(f'Missing display field: {name}')
            return match.group(1)
        modes = []
        for match in re.finditer(
            r'^  mode (\d+): res:(\d+)x(\d+) hz:([\d.]+) color_depth:(\d+)([^\n]*)',
            block, re.M,
        ):
            number, width, height, hz, depth, suffix = match.groups()
            modes.append(dict(number=int(number), width=int(width), height=int(height),
                              hz=float(hz), depth=int(depth), scaled='scaling:on' in suffix))
        if not modes:
            raise ValueError('No modes for ' + block.splitlines()[0])
        # Prefer unscaled modes on ties. HiDPI logical sizes are not physical resolution.
        best = max(modes, key=lambda m: (m['width'] * m['height'], m['hz'],
                                        m['depth'], not m['scaled']))
        kind = field('Type')
        if 'built in' in kind:
            # Keep laptop text readable with a HiDPI logical resolution.
            preferred = [m for m in modes if m['scaled']
                         and (m['width'], m['height']) == (1470, 956)]
            if preferred:
                best = max(preferred, key=lambda m: (m['hz'], m['depth']))
        inches = re.search(r'([\d.]+) inch', kind)
        result.append(dict(id=block.splitlines()[0], internal='built in' in kind,
                           inches=float(inches.group(1)) if inches else 0,
                           best=best, resolution=field('Resolution'), hz=float(field('Hertz')),
                           depth=int(field('Color Depth')), scaled=field('Scaling') == 'on',
                           origin=field('Origin').split(' ')[0]))
    return result


def main():
    screens = displays()
    if not screens:
        return
    screens.sort(key=lambda s: (not s['internal'], s['inches'],
                               s['best']['width'] * s['best']['height'], s['id']), reverse=True)
    # Keep the default left-side laptop layout for other monitors.
    laptop_on_right = screens[0]['id'] in LAPTOP_RIGHT_OF
    left, right = 0, 0
    arguments, changed = [], False
    for index, screen in enumerate(screens):
        mode = screen['best']
        if index == 0:
            x, right = 0, mode['width']
        elif screen['internal'] and not laptop_on_right:
            left -= mode['width']
            x = left
        else:
            x = right
            right += mode['width']
        origin = f'({x},0)'
        resolution = f"{mode['width']}x{mode['height']}"
        scaling = 'on' if mode['scaled'] else 'off'
        arguments.append(f"id:{screen['id']} res:{resolution} hz:{mode['hz']:g} "
                         f"color_depth:{mode['depth']} scaling:{scaling} origin:{origin}")
        changed |= (screen['resolution'] != resolution or screen['hz'] != mode['hz']
                    or screen['depth'] != mode['depth'] or screen['scaled'] != mode['scaled']
                    or screen['origin'] != origin)
    if '--dry-run' in sys.argv:
        print(('Would apply: ' if changed else 'Already configured: ')
              + shlex.join([DISPLAYPLACER, *arguments]))
    elif changed:
        subprocess.run([DISPLAYPLACER, *arguments], check=True, timeout=8)
        print('Applied display policy', flush=True)


if __name__ == '__main__':
    main()
