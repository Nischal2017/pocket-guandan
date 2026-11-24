"""The 400 × 215 printed table. Artwork stays clear of the system footer."""
from functools import lru_cache

from ink import Canvas
from ui_text import SEATS, face, language, message, move_label, ui

_W, _H = 24, 43

# Cut on a square grid, with slab serifs and open counters that survive 1-bit
# output. Ten has its own condensed block, not two squeezed font glyphs.
_TYPE = {
    '2': ('.###.', '##.##', '...##', '..##.', '.##..', '##...', '#####'),
    '3': ('####.', '...##', '...##', '.###.', '...##', '#..##', '.###.'),
    '4': ('...#.', '..##.', '.#.#.', '#..#.', '#####', '...#.', '..###'),
    '5': ('#####', '##...', '####.', '...##', '...##', '#..##', '.###.'),
    '6': ('..###', '.##..', '##...', '####.', '##.##', '##.##', '.###.'),
    '7': ('#####', '#...#', '...##', '..##.', '..#..', '.##..', '.##..'),
    '8': ('.###.', '##.##', '##.##', '.###.', '##.##', '##.##', '.###.'),
    '9': ('.###.', '##.##', '##.##', '.####', '...##', '..##.', '###..'),
    '10': ('.#...###.', '##..##.##', '.#..##.##', '.#..##.##', '.#..##.##', '.#..##.##', '###..###.'),
    'J': ('..###', '...##', '...##', '...##', '...##', '##.##', '.###.'),
    'Q': ('.###.', '##.##', '##.##', '##.##', '##.##', '.###.', '...##'),
    'K': ('##.##', '##.#.', '###..', '###..', '##.#.', '##.##', '##.##'),
    'L': ('##...', '##...', '##...', '##...', '##...', '##...', '#####'),
    'H': ('##.##', '##.##', '##.##', '#####', '##.##', '##.##', '##.##'),
    'A': ('..#..', '.###.', '.#.#.', '##.##', '#####', '##.##', '##.##'),
}
_PIPS = {
    '♠': ('....#....', '...###...', '..#####..', '.#######.', '#########',
          '#########', '.###.###.', '....#....', '..#####..'),
    '♥': ('.##...##.', '####.####', '#########', '#########', '.#######.',
          '..#####..', '...###...', '....#....'),
    '♦': ('....#....', '...###...', '..#####..', '.#######.', '#########',
          '.#######.', '..#####..', '...###...', '....#....'),
    '♣': ('...###...', '..#####..', '...###...', '.##.#.##.', '#########',
          '#########', '.##.#.##.', '....#....', '..#####..'),
    '王': ('#...#...#', '##.###.##', '.#######.', '.#######.', '..#####..',
          '.........', '..#####..'),
}
_FLEUR = ('....#....', '...#.#...', '..#...#..', '.#..#..#.', '#..###..#',
          '.#..#..#.', '..#...#..', '...#.#...', '....#....')


@lru_cache(maxsize=None)
def _cuts(rows):
    """Runs of ink on each scanline, shared across impressions."""
    runs = []
    for y, row in enumerate(rows):
        x = 0
        for run in row.split('.'):
            if run:
                runs.append((x, y, len(run)))
            x += len(run) + 1
    return tuple(runs)


def _stamp(c, x, y, rows, white=False, sx=1, sy=1):
    for dx, dy, length in _cuts(rows):
        c.box(x + dx * sx, y + dy * sy, length * sx, sy, white)


def _pip(c, x, y, suit, white=False):
    _stamp(c, x, y, _PIPS[suit], white)


def _tile(c, x, y, w, h, white=0):
    c.box(x + 1, y, w - 2, h, white)
    c.box(x, y + 1, w, h - 2, white)


def _card(c, x, y, card, selected, cursor, lift=None, level=2, eligible=False, lang='en'):
    rank, suit, _ = card
    if lift is None:
        lift = 5 if selected else 0
    y -= max(0, min(5, lift))
    _tile(c, x + 1, y + 2, _W, _H)  # the stock beneath the face
    _tile(c, x, y, _W, _H)
    _tile(c, x + 1, y + 1, _W - 2, _H - 2, not selected)
    mark = face(rank, lang, short=True)
    if mark in _TYPE:
        glyph = _TYPE[mark]
        sx = 2 if mark == '10' else 3
        _stamp(c, x + (_W - len(glyph[0]) * sx) // 2, y + 5, glyph, selected, sx, 3)
    else:
        c.text(x + 12, y + 24, mark, 21, True, selected, 'center')
    _pip(c, x + 7, y + 29, suit, selected)
    # On the gift tray, legal choices have a dark top edge. The printed
    # four-point mark follows the physical heart of the active level.
    if eligible:
        c.box(x + 3, y + 2, 18, 2, selected)
    else:
        c.box(x + 3, y + 3, 3, 1, selected)
    if rank == level and suit == '♥':
        _stamp(c, x + 16, y + 34, ('..#..', '..#..', '#####', '..#..', '..#..'), selected)
    else:
        c.box(x + 18, y + 39, 3, 1, selected)
    if cursor:
        for dy in range(5):
            c.box(x + 11 - dy, y + _H + 4 + dy, 1 + 2 * dy, 1)


def _header(c, t, lang):
    _tile(c, 6, 4, 45, 21)
    _tile(c, 7, 5, 43, 19, 1)
    level = getattr(t.game, 'level', 2)
    c.text(28, 20, f'{ui(lang, "打")} {face(level, lang)}', 15, True, align='center', maxw=39)
    match = getattr(t, 'match', None)
    active_seat = None if t.game.over else t.game.turn
    if getattr(match, 'phase', '') == 'tribute':
        active_seat = match.actor
    for column, seat in enumerate((3, 2, 1, 0)):
        x = 99 + column * 85
        active = active_seat == seat
        if active:
            _tile(c, x - 34, 4, 68, 21)
        count = len(t.game.hands[seat])
        label = SEATS[lang][seat] + (f'  {count}' if count <= 10 else '')
        c.text(x, 20, label, 14, True, active, 'center', maxw=63)


def _corners(c):
    # Only the corners of the playing field are inked; leave a quiet well.
    for x, dx in ((7, 1), (392, -1)):
        for y, dy in ((31, 1), (89, -1)):
            c.box(min(x, x + 8 * dx), y, 9, 1)
            c.box(x, min(y, y + 4 * dy), 1, 5)
            c.box(x + 3 * dx, y + 3 * dy, 1, 1)


def _table(c, t, lang):
    _corners(c)
    level = getattr(t.game, 'level', 2)
    played = t.top_cards
    if played and t.game.owner is not None:
        # Center the caption and the played cards together. A pass changes the
        # active header seat, not the provenance of the paper in the well.
        n = len(played)
        wild = any(r == level and s == '♥' for r, s, _ in played)
        caption = 98 if wild else 90
        stride = min(28, (364 - caption - _W) // max(1, n - 1))
        left = (400 - (caption + _W + (n - 1) * stride)) // 2 + caption
        c.text(left - 9, 50 if wild else 60, ui(lang, '出牌：') + SEATS[lang][t.game.owner],
               13, True, align='right', maxw=caption - 9)
        if wild:
            c.text(left - 9, 68, move_label(t.game.top, lang), 13, align='right', maxw=caption - 9)
        for i, card in enumerate(played):
            _card(c, left + i * stride, 31, card, False, False, level=level, lang=lang)
    elif getattr(t, 'notice', ''):
        c.text(200, 61, message(t.notice, lang), 17, True, align='center', maxw=344)
    elif getattr(t, 'deal', 1) == 1 and not any(getattr(t.game, 'last', ())):
        # Identify the game without consuming space during a trick.
        c.text(200, 61, ui(lang, '掼蛋'), 18, True, align='center')
    else:
        _stamp(c, 195, 50, _FLEUR)
        for x in (180, 213):
            c.box(x, 54, 7, 1)
    label = message(t.feedback, lang)
    if not label and t.selected:
        move = t.choice()
        if move is not None:
            label = move_label(move, lang)
            count = getattr(t, 'alternatives', 0)
            if count > 1:
                label += f'   {getattr(t, "mode", 0) + 1}/{count}'
    if label:
        c.text(200, 92, label, 14, True, align='center', maxw=330)


def _tribute(c, t, lang):
    _corners(c)
    # The exchange message identifies both parties and the action. Show only
    # the actual nominated card, never the trick from the previous round.
    card = next((v for v in t.game.hands[0] if v[2] == t.tribute_selected), None)
    if card is not None and t.match.actor == 0:
        _card(c, 327, 37, card, False, False, level=getattr(t.game, 'level', 2), lang=lang)
        c.text(172, 66, message(t.match.message, lang), 20, True, align='center', maxw=282)
    else:
        c.text(200, 66, message(t.match.message, lang), 20, True, align='center', maxw=346)
    if getattr(t, 'feedback', ''):
        c.text(200, 91, message(t.feedback, lang), 14, True, align='center', maxw=330)


def _results(c, g, match, lang):
    seats = SEATS[lang]
    head = g.finish[0]
    champion = getattr(match, 'champion', None)
    title = ('本局结算' if champion is None else
             ('我方' if champion % 2 == 0 else '对方') + '赢得整场')
    c.text(200, 53, ui(lang, title), 16, True, align='center', maxw=150)
    for x in (38, 280):
        c.box(x, 46, 82, 1)
    # A keepsake face for the head finisher, and a short unboxed score slip.
    x, y, w, h = 43, 66, 115, 126
    _tile(c, x + 2, y + 3, w, h)
    _tile(c, x, y, w, h)
    _tile(c, x + 2, y + 2, w - 4, h - 4, 1)
    _stamp(c, x + 8, y + 8, _FLEUR)
    _stamp(c, x + w - 17, y + h - 17, _FLEUR)
    _pip(c, x + 53, y + 17, '王')
    c.text(x + 57, y + 45, ui(lang, '头游'), 14, True, align='center')
    c.text(x + 57, y + 84, seats[head], 33, True, align='center', maxw=104)
    c.text(x + 57, y + 107, ui(lang, '我方胜' if head % 2 == 0 else '对方胜'), 13, align='center', maxw=108)
    finished = [s for s in g.finish if not g.hands[s]]
    rows = list(zip(('二游', '三游', '末游'), (seats[s] for s in finished[1:])))
    # Some engines append live seats to finish on team completion. They did
    # not actually finish in that order: print one unranked line for them.
    remaining = [seats[s] for s in range(4) if g.hands[s]]
    if remaining:
        rows.append(('未出完', ' · '.join(remaining)))
    top = 115 - (len(rows) - 1) * 13
    for i, (place, names) in enumerate(rows):
        baseline = top + i * 26
        c.text(183, baseline, ui(lang, place), 14, maxw=60)
        c.text(359, baseline, names, 19, True, align='right', maxw=114)
        if i + 1 < len(rows):
            c.box(183, baseline + 5, 176, 1)
    if match is not None:
        ours, theirs = (face(r, lang) for r in match.levels)
        c.text(183, 165, f'{ui(lang, "我方")} {ours}', 14)
        c.text(359, 165, f'{ui(lang, "对方")} {theirs}', 14, align='right')
        c.text(271, 187, ui(lang, 'A  新比赛' if champion is not None else 'A  下一局'),
               13, True, align='center')
        c.text(200, 209, message(match.summary, lang), 15, True, align='center', maxw=378)


# A held hand: columns are ranks, depth within a column is physical copies.
# All copies share a local x-axis. Every exposed strip owns its own index + pip.
from math import radians
from ink import bind, P, D
_save=bind('save',None,P); _restore=bind('restore',None,P)
_translate=bind('translate',None,P,D,D); _rotate=bind('rotate',None,P,D)


def _corner(c,rank,suit,strip,invert,lang):
    mark=face(rank,lang,short=True); glyph=_TYPE.get(mark)
    # A deep bomb needs a shallow strip: put its suit beside, not under, its rank.
    narrow=strip<24
    sy=1 if strip<17 else 2
    sx=1 if mark=='10' and narrow else 2
    if glyph:
        _stamp(c,3,2,glyph,invert,sx,sy)
        right=3+len(glyph[0])*sx
    else:
        c.text(3,14,mark,13,True,invert);right=17
    if narrow:_pip(c,right+1,2,suit,invert)
    else:_pip(c,4,17,suit,invert)


def _pile_hand(c,t,lang):
    piles=t.piles()
    if not piles:return
    n=len(piles); span=max(1,n-1)
    pitch=min(31,342//span); w=min(51,pitch+10); h=42
    start=(400-(pitch*(n-1)+w))//2
    for k,group in enumerate(piles):
        pos=(2*k-(n-1))/span
        x=start+k*pitch
        base=204+round(4*pos*pos)
        # Keep the card indexes above the front face within the available felt.
        band=min(28,(base-h-96)//max(1,len(group)-1))
        _save(c.c)
        try:
            _translate(c.c,x,base);_rotate(c.c,radians(pos*4.0))
            for j,index in enumerate(group):
                rank,suit,uid=t.hand[index];chosen=uid in t.selected
                y=-h-(len(group)-1-j)*band
                # Avoid hiding a narrow bomb strip by raising its neighbour.
                rise=min(3,max(0,band-11),t.lift(uid,chosen))
                _save(c.c);_translate(c.c,0,y-rise)
                try:
                    _tile(c,1,1,w,h);_tile(c,0,0,w,h)
                    _tile(c,1,1,w-2,h-2,not chosen)
                    if chosen:c.box(2,1,w-4,1,1)
                    front=j==len(group)-1
                    _corner(c,rank,suit,28 if front else band,chosen,lang)
                    if front:
                        _pip(c,w//2,27,suit,chosen)
                        if (rank,suit)==(t.game.level,'♥'):
                            _stamp(c,w//2+10,25,_FLEUR,chosen)
                    if t.human_turn and index==t.cursor:
                        # A notch on this exposed corner, independent of selection.
                        for z in range(3):c.box(pitch-4+z,3+z,1,5-2*z,int(chosen))
                finally:_restore(c.c)
            if t.human_turn and t.cursor in group:c.box(2,2,pitch-4,2)
        finally:_restore(c.c)


def _hand(c, t, tribute, lang):
    if not tribute:
        _pile_hand(c, t, lang)
        return
    hand = t.game.hands[0]
    human = t.match.actor == 0
    choices = t.eligible_ids if human else ()
    level = getattr(t.game, 'level', 2)
    for j, card in enumerate(hand):
        row, col = divmod(j, 14)
        width = min(14, len(hand) - 14 * row)
        x = (400 - ((width - 1) * 28 + _W + 1)) // 2 + col * 28
        uid = card[2]
        selected = human and uid == t.tribute_selected
        eligible = uid in choices
        rise = 2 if eligible and not selected else None
        y = 138 if len(hand) <= 14 else 104 + row * 56
        _card(c, x, y, card, selected, human and j == t.cursor, rise, level, eligible, lang=lang)


def render(t, lang=None) -> bytes:
    """Render without mutating the table. An explicit language overrides Table.lang."""
    lang = language(getattr(t, 'lang', 'en') if lang is None else lang)
    c = Canvas()
    _header(c, t, lang)
    match = getattr(t, 'match', None)
    phase = getattr(match, 'phase', 'result' if t.game.over else 'play')
    if phase in ('result', 'match_over'):
        _results(c, t.game, match, lang)
    else:
        if phase == 'tribute':
            _tribute(c, t, lang)
        else:
            _table(c, t, lang)
        _hand(c, t, phase == 'tribute', lang)
    return c.finish()
