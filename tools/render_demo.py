#!/usr/bin/env python3
"""Rebuild docs/media from a real deal. Needs Python 3, libcairo, and ffmpeg.

Run: python3 tools/render_demo.py
The native PNGs preserve all 240 rows. For the GIF, only the blank system
footer is cropped; guide captions are outside the captured playing area.
"""
import ctypes
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ink
from pocket import Table

OUT = ROOT / 'docs' / 'media'


class Replay:
    now = 0.

    def monotonic(self):
        return self.now

    def deal(self):
        self.table = Table(0, lang='en')
        self.table.focus(True)

    def send(self, *codes):
        for code in codes:
            self.now += .30
            self.table.input(code, self.now)

    def frame(self):
        self.now += .12  # sample after the real 105 ms card lift
        data = self.table.frame()
        assert len(data) == 12000 and data[215*50:] == bytes([255]) * 1250
        return data


def capture():
    # Advance only the monotonic clock: hands, choices, AI, and ownership all
    # come from the live game. No hand or scene fixtures are injected.
    r = Replay()
    with patch('pocket.time', r):
        r.deal()
        t = r.table
        shots = []

        def shot(caption, centiseconds):
            shots.append((r.frame(), caption, centiseconds))

        shot('Cards are stacked by rank.', 150)
        r.send(8, 8)  # swipe right twice: 3, 6, 7
        assert t.hand[t.cursor][0] == 7
        shot('Swipe right to the 7s.', 105)
        r.send(5)
        shot('Swipe up to select one 7.', 125)
        r.send(5)
        assert t.choice().kind == 'pair'
        shot('Swipe up again for a pair.', 150)
        stacked = shots[-1][0]
        r.send(1, 2)  # A press and short release
        assert t.game.owner == 0 and t.game.top.ranks == (7, 7)
        shot('Tap A to play your pair.', 160)
        r.now += 1.1
        t.tick()  # genuine response from the next seat
        assert t.game.owner == 1 and t.game.top.ranks == (13, 13)
        shot('The next seat beats your 7s with kings.', 195)

        r.deal()  # replay the same deck with a different lead
        r.send(8, 8, 5, 5, 8, 5, 5)  # select two 7s and two 8s
        r.send(7, 7, 7, 7)  # move left from 8 past 7, 6, 3 to the wild pile
        assert r.table.hand[r.table.cursor][:2] == (2, '♥')
        r.send(5, 1)
        r.now += .40  # long A release cycles wild declarations
        r.send(2)
        assert r.table.alternatives == 2 and r.table.mode == 1
        return shots, stacked, r.frame()


def guide_band(index, count, caption):
    """RGB pixels for the editorial caption, separate from the LCD capture."""
    width, height = 800, 68
    sf = ink.surface(1, width, height)  # Cairo RGB24 (native-endian XRGB)
    c = ink.create(sf)
    dark, mint, white = (.09, .16, .19), (.49, .88, .79), (.99, .99, .96)

    def box(x, y, w, h, rgb):
        ink.color(c, *rgb); ink.rect(c, x, y, w, h); ink.fill(c)

    def label(x, y, s, px, rgb, family=b'Liberation Sans'):
        ink.color(c, *rgb); ink.select(c, family, 0, 1); ink.size(c, px)
        ink.move(c, x, y); ink.show(c, s.encode())

    try:
        box(0, 0, width, height, dark)
        label(24, 24, 'REPLAY', 12, mint, b'Liberation Mono')
        label(23, 50, f'{index:02} / {count:02}', 18, white, b'Liberation Mono')
        box(121, 18, 2, 33, mint)
        label(147, 44, caption, 27, white)
        ink.flush(sf)
        native = ctypes.string_at(ink.data(sf), width * height * 4)
        out = bytearray(width * height * 3)
        channels = (2, 1, 0) if sys.byteorder == 'little' else (1, 2, 3)
        for i, j in enumerate(channels):
            out[i::3] = native[j::4]
        return out
    finally:
        ink.destroy(c); ink.free(sf)


def write_gif(shots, temp):
    # Expand each LCD bit to two identical RGB pixels and double each row.
    tiles = [b''.join(bytes([255 if v & (128 >> i) else 0])*6 for i in range(8))
             for v in range(256)]
    manifest = []
    for index, (lcd, caption, delay) in enumerate(shots, 1):
        name = f'{index}.ppm'
        with (temp / name).open('wb') as f:
            f.write(b'P6\n800 498\n255\n')
            for y in range(215):
                row = b''.join(tiles[v] for v in lcd[y*50:(y+1)*50])
                f.write(row * 2)
            f.write(guide_band(index, len(shots), caption))
        manifest.extend([f'file {name}', 'option framerate 100', f'duration {delay/100:.2f}'])
    (temp / 'timeline').write_text('\n'.join(manifest) + '\n')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0',
                    '-i', 'timeline', '-filter_complex',
                    'split[a][b];[a]palettegen[p];[b][p]paletteuse=dither=none',
                    '-fps_mode', 'vfr', '-loop', '0', '-final_delay', str(shots[-1][2]),
                    str(OUT / 'pocket-guandan-demo.gif')], cwd=temp, check=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    shots, stacked, wildcard = capture()
    with TemporaryDirectory() as temp:
        write_gif(shots, Path(temp))
    ink.png(stacked, OUT / 'stacked-hand.png')
    ink.png(wildcard, OUT / 'wildcard-choice.png')


if __name__ == '__main__':
    main()
