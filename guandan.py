"""Guandan for four seats (partners 0/2 and 1/3).

Game is rank-only at level 2; PhysicalGame supports suits and a configurable
level per deal. Runs use natural ranks, with A low or high but no wraparound.
Outside runs the level rank beats all non-jokers. Neither game manages tribute
or progression between deals.
"""
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
import random


_RANKS = tuple(range(2, 17))


def _rank_power(level):
    """Increasing strength outside runs; level 2 matches the rank-only game."""
    if type(level) is not int or not 2 <= level <= 14:
        raise ValueError('级牌必须为 2 至 A')
    order = [r for r in range(2, 15) if r != level] + [level, 15, 16]
    return {r: i for i, r in enumerate(order)}


_POWER = _rank_power(2)
_FACE = {11: 'J', 12: 'Q', 13: 'K', 14: 'A', 15: '小王', 16: '大王'}
_GROUPS = {1: 'single', 2: 'pair', 3: 'triple'}
_RUNS = {'straight': (5, 1), 'pair_run': (3, 2), 'triple_run': (2, 3)}
_NAMES = {'single': '单张', 'pair': '对子', 'triple': '三张', 'house': '三带二',
          'straight': '顺子', 'pair_run': '三连对', 'triple_run': '钢板',
          'joker_bomb': '天王炸'}
# Look up canonical display order AND comparative strength of every legal run.
_RUN_TABLE = {}
for _kind, (_width, _copies) in _RUNS.items():
    for _start in range(1, 16 - _width):
        _order = tuple(14 if r == 1 else r for r in range(_start, _start + _width))
        _RUN_TABLE[_kind, frozenset(_order)] = (_order, _start)


def _classify(cards):
    counts = Counter(cards)
    if not cards or any(type(r) is not int or r not in _POWER or
                        n > (2 if r >= 15 else 8) for r, n in counts.items()):
        raise ValueError('点数或张数无效')
    size = len(cards)
    if len(counts) == 1:
        r = cards[0]
        return cards, _GROUPS.get(size, 'bomb'), _POWER[r]
    if counts == {15: 2, 16: 2}:
        return (15, 15, 16, 16), 'joker_bomb', 0
    if sorted(counts.values()) == [2, 3]:
        a, b = sorted(counts, key=counts.get, reverse=True)
        return (a,) * 3 + (b,) * 2, 'house', _POWER[a]
    for kind, (width, copies) in _RUNS.items():
        if len(counts) == width and all(n == copies for n in counts.values()):
            run = _RUN_TABLE.get((kind, frozenset(counts)))
            if run is not None:
                ranks, power = run
                return tuple(r for r in ranks for _ in range(copies)), kind, power
    raise ValueError('不是合法牌型')


@dataclass(frozen=True)
class Move:
    """Move(cards) validates and orders ranks; equal moves have equal cards."""
    cards: tuple
    kind: str = field(init=False, compare=False)
    power: int = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        cards, kind, power = _classify(tuple(self.cards))
        object.__setattr__(self, 'cards', cards)
        object.__setattr__(self, 'kind', kind)
        object.__setattr__(self, 'power', power)

    @property
    def label(self):
        return f'{len(self.cards)}张炸弹' if self.kind == 'bomb' else _NAMES[self.kind]

    def beats(self, other):
        if other is None:
            return True
        if self.kind == 'joker_bomb' or other.kind == 'joker_bomb':
            return self.kind == 'joker_bomb' and other.kind != 'joker_bomb'
        if self.kind == 'bomb':
            return (other.kind != 'bomb' or
                    (len(self.cards), self.power) > (len(other.cards), other.power))
        return self.kind == other.kind and self.power > other.power


@lru_cache(maxsize=1024)
def _move(cards):
    return Move(cards)


@lru_cache(maxsize=128)
def _moves(hand):
    count = Counter(hand)
    moves = []
    for r, n in count.items():
        moves.extend(_move((r,) * i) for i in range(1, n + 1))
        if n >= 3:
            moves.extend(_move((r,) * 3 + (s,) * 2) for s, m in count.items()
                         if s != r and m >= 2)
    for (kind, _), (ranks, _) in _RUN_TABLE.items():
        copies = _RUNS[kind][1]
        if all(count[r] >= copies for r in ranks):
            moves.append(_move(tuple(r for r in ranks for _ in range(copies))))
    if count[15] == count[16] == 2:
        moves.append(_move((15, 15, 16, 16)))
    return tuple(moves)


class Game:
    """Game(seed=None) deals 108 cards; seat 0 leads. All seats can use play()."""

    def __init__(self, seed=None):
        deck = [r for r in _RANKS for _ in range(8 if r <= 14 else 2)]
        random.Random(seed).shuffle(deck)
        self.hands = [sorted(deck[i::4], key=_POWER.get) for i in range(4)]
        self._start_round()

    def _start_round(self):
        self.turn = 0
        self.top = self.owner = None
        self.finish = []
        self.over = False
        self.last = [''] * 4
        self._passed = set()

    def options(self):
        """All legal plays, recommendation first. None is pass, never a lead."""
        if self.over:
            return []
        hand = self.hands[self.turn]
        counts = Counter(hand)
        legal = [m for m in _moves(tuple(hand)) if m.beats(self.top)]
        has_rocket = counts[15] == counts[16] == 2

        def preference(m):
            # Finish if possible. Otherwise reserve bombs/jokers and avoid
            # breaking up pairs/triples. On lead, shed long cheap groups first.
            used = Counter(m.cards)
            split_bomb = any(counts[r] >= 4 and n < counts[r] for r, n in used.items())
            split_rocket = has_rocket and m.kind != 'joker_bomb' and max(used) >= 15
            fragmented = sum(1 for r, n in used.items() if n < counts[r])
            return (len(m.cards) != len(hand), m.kind in ('bomb', 'joker_bomb'),
                    m.kind == 'joker_bomb', split_rocket or split_bomb,
                    len(m.cards) if m.kind == 'bomb' else -len(m.cards),
                    fragmented, m.power, sum(_POWER[r] for r in m.cards), m.cards)

        legal.sort(key=preference)
        if self.top is not None:
            # Don't overtake partner except to go out. Against an opponent,
            # save bombs unless going out or an opponent is close to doing so.
            partner_up = self.owner == (self.turn + 2) % 4
            danger = any(0 < len(self.hands[i]) <= 3 for i in range(4)
                         if (i - self.turn) % 2)
            index = next((i for i, m in enumerate(legal)
                          if len(m.cards) != len(hand) and
                          (partner_up or (not danger and m.kind in ('bomb', 'joker_bomb')))),
                         len(legal))
            legal.insert(index, None)
        return legal

    def bot_move(self):
        """Choose but do not play the current seat's move; None if pass/over."""
        choices = self.options()
        return choices[0] if choices else None

    def _next_live(self, seat):
        return next(i for d in range(1, 5) if self.hands[i := (seat + d) % 4])

    def _valid_move(self, move):
        return isinstance(move, Move) and move.beats(self.top)

    def _describe(self, move):
        return move.label + ' ' + ' '.join(_FACE.get(r, str(r)) for r in move.cards)

    def play(self, move):
        """Apply one Move or None. Illegal actions raise ValueError without mutation."""
        if self.over:
            raise ValueError('本局已结束')
        seat = self.turn
        if move is None:
            if self.top is None:
                raise ValueError('领出不能过牌')
            self.last[seat] = '过'
            self._passed.add(seat)
            if all(not h or i == self.owner or i in self._passed
                   for i, h in enumerate(self.hands)):
                # If the winner went out, their live partner inherits the wind.
                leader = self.owner
                if not self.hands[leader]:
                    partner = (leader + 2) % 4
                    leader = partner if self.hands[partner] else self._next_live(leader)
                self.turn = leader
                self.top = self.owner = None
                self._passed.clear()
            else:
                self.turn = self._next_live(seat)
            return

        hand = self.hands[seat]
        if not self._valid_move(move):
            raise ValueError('必须压过桌面牌')
        if Counter(move.cards) - Counter(hand):
            raise ValueError('所选牌不在手中')
        for r in move.cards:
            hand.remove(r)
        self.top, self.owner = move, seat
        self._passed.clear()
        self.last[seat] = self._describe(move)
        if not hand:
            self.finish.append(seat)
            if (seat + 2) % 4 in self.finish:
                # The trailing two seats tie if the winners went 1-2. List
                # those unplayed places clockwise from the last finisher.
                self.finish.extend(i for d in range(1, 4)
                                   if (i := (seat + d) % 4) not in self.finish)
                self.over = True
                self.top = self.owner = None
                return
        self.turn = self._next_live(seat)


# Physical engine. A declaration is a logical pattern, not just a pile of cards.
# Only meaningful differences are represented: interchanging two identical
# wilds or declaring an irrelevant suit in a pair does not create another play.
SUITS = ('♠', '♥', '♣', '♦')
_BOMBS = frozenset(('bomb', 'straight_flush', 'joker_bomb'))


def physical_deck():
    faces = [(r, s) for r in range(2, 15) for s in SUITS] + [(15, '王'), (16, '王')]
    return [(r, s, i) for i, (r, s) in enumerate(faces * 2)]


def _face(r):
    return _FACE.get(r, str(r))


def _tier(kind, n):
    if kind == 'joker_bomb':
        return 99
    if kind == 'straight_flush':
        return 11
    return 2 * n if kind == 'bomb' else 0


@dataclass(frozen=True, slots=True)
class PhysicalMove:
    cards: tuple
    kind: str
    power: int
    ranks: tuple
    suit: str | None = None
    level: int = 2

    def beats(self, other):
        if other is None:
            return True
        tier, theirs = _tier(self.kind, len(self.cards)), _tier(other.kind, len(other.cards))
        if tier != theirs:
            return tier > theirs
        return self.kind == other.kind and self.power > other.power

    @property
    def label(self):
        a, b = _face(self.ranks[0]), _face(self.ranks[-1])
        if self.kind == 'bomb':
            return f'{len(self.cards)}张炸弹 {a}'
        if self.kind == 'straight_flush':
            return f'同花顺 {self.suit}{a}–{b}'
        name = _NAMES[self.kind]
        if self.kind == 'joker_bomb':
            return name
        if self.kind == 'house':
            return f'{name} {a}带{b}'
        if self.kind in _RUNS:
            return f'{name} {a}–{b}'
        return f'{name} {a}'

    @property
    def description(self):
        wilds = [f'♥{_face(self.level)}→{self.suit or ""}{_face(r)}'
                 for c, r in zip(self.cards, self.ranks)
                 if c[:2] == (self.level, '♥') and (r != self.level or self.suit not in (None, '♥'))]
        return ' '.join([self.label, *wilds])


@dataclass(frozen=True, slots=True)
class _Pattern:
    kind: str
    power: int
    need: tuple        # (rank, number needed) in declaration order
    ranks: tuple
    suit: str | None
    tier: int


def _patterns(level, rank_power):
    def make(kind, power, need, suit=None):
        ranks = tuple(r for r, n in need for _ in range(n))
        return _Pattern(kind, power, need, ranks, suit, _tier(kind, len(ranks)))

    for r in _RANKS:
        # Two wilds can extend the eight natural copies to ten. At the level rank
        # there are only eight cards total; wilds cannot make more jokers.
        for n in range(1, (2 if r > 14 else 8 if r == level else 10) + 1):
            yield make(_GROUPS.get(n, 'bomb'), rank_power[r], ((r, n),))
        if r <= 14:
            for pair in _RANKS:
                if r != pair:
                    yield make('house', rank_power[r], ((r, 3), (pair, 2)))
    for (kind, _), (order, power) in _RUN_TABLE.items():
        need = tuple((r, _RUNS[kind][1]) for r in order)
        yield make(kind, power, need)
        if kind == 'straight':
            for suit in SUITS:
                yield make('straight_flush', power, need, suit)
    yield make('joker_bomb', 0, ((15, 2), (16, 2)))


class _LevelRules:
    """Pattern indexes shared by all deals at this level."""

    def __init__(self, level):
        self.power = _rank_power(level)
        self.level = level
        self.wild = (level, '♥')
        self.patterns = tuple(_patterns(level, self.power))
        self.flushes = tuple(p for p in self.patterns if p.kind == 'straight_flush')
        self.by_size = {n: tuple(p for p in self.patterns if len(p.ranks) == n)
                        for n in range(1, 11)}

    @lru_cache(maxsize=512)
    def replies(self, kind, size, power):
        tier = _tier(kind, size)
        return tuple(p for p in self.patterns if p.tier > tier or
                     (p.kind == kind and p.tier == tier and p.power > power))


@lru_cache(maxsize=13, typed=True)
def _level_rules(level):
    return _LevelRules(level)


def _generate(cards, patterns, rules):
    """Match small fixed templates, not hand subsets. Prefer natural cards.

    On a hand, one inexpensive physical realization per feasible declaration.
    On an exact-size selection each match necessarily uses every selected ID.
    Same-suit sequences can declare an ordinary straight OR a straight flush.
    """
    by_rank = [[] for _ in range(17)]
    by_suit = {s: [[] for _ in range(17)] for s in SUITS}
    wilds = []
    for c in cards:
        r, s, _ = c
        if c[:2] == rules.wild:
            wilds.append(c)
        else:
            by_rank[r].append(c)
            if r <= 14:
                by_suit[s][r].append(c)
    wilds.sort()
    nw = len(wilds)
    for p in patterns:
        if len(p.ranks) > len(cards):
            continue
        pool = by_suit[p.suit] if p.suit else by_rank
        spent = 0
        for r, n in p.need:
            deficit = n - len(pool[r])
            if deficit > 0:
                spent += deficit
                if spent > nw or r >= 15:
                    break
        else:
            if spent == len(p.ranks) and p.ranks[0] != rules.level:
                continue  # a lone wild or a pair of bare wilds stays at the level rank
            picked = []
            i = 0
            for r, n in p.need:
                natural = sorted(pool[r][:n])
                picked.extend(natural)
                j = i + n - len(natural)
                picked.extend(wilds[i:j])
                i = j
            yield PhysicalMove(tuple(picked), p.kind, p.power, p.ranks, p.suit, rules.level)


def interpretations(cards, level=2):
    """All declarations of these exact physical cards; [] for invalid selections."""
    cards = tuple(cards)
    rules = _level_rules(level)
    if len(cards) not in rules.by_size:
        return []
    ids, faces = set(), Counter()
    for c in cards:
        if not isinstance(c, tuple) or len(c) != 3:
            return []
        r, s, i = c
        if (type(r) is not int or r not in rules.power or type(i) is not int or i in ids or
                s not in (SUITS if r <= 14 else ('王',))):
            return []
        ids.add(i)
        faces[r, s] += 1
        if faces[r, s] > 2:
            return []
    return list(_generate(sorted(cards), rules.by_size[len(cards)], rules))


class PhysicalGame(Game):
    """Two shuffled 54-card decks. Pass and finish semantics are shared with Game."""

    def __init__(self, seed=None, level=2):
        self._rules = _level_rules(level)
        deck = physical_deck()
        random.Random(seed).shuffle(deck)
        self.hands = [sorted(deck[i::4], key=self.card_sort_key)
                      for i in range(4)]
        self._start_round()

    @property
    def level(self):
        return self._rules.level

    def card_power(self, card):
        """Strength of one physical card outside runs (also used for tribute)."""
        return self._rules.power[card[0]]

    def card_sort_key(self, card):
        return self.card_power(card), card[1], card[2]

    def interpret(self, cards):
        return interpretations(cards, self.level)

    def legal_interpretations(self, cards):
        cards = tuple(cards)
        if self.over or any(c not in self.hands[self.turn] for c in cards):
            return []
        return [m for m in self.interpret(cards) if m.beats(self.top)]

    def _valid_move(self, move):
        # Do not trust declarations (including forged power or assignments).
        return (isinstance(move, PhysicalMove) and move in self.interpret(move.cards)
                and move.beats(self.top))

    def _describe(self, move):
        return move.description

    def options(self):
        if self.over:
            return []
        hand, top = self.hands[self.turn], self.top
        rules = self._rules
        patterns = rules.replies(top.kind, len(top.cards), top.power) if top else rules.patterns
        cards = sorted(hand)
        # Reserve one ready straight flush (prefer a natural, then a high
        # one). For other declarations take spare suits/copies first. This
        # avoids both combinatorial suit branching and needless bomb splits.
        flush = max(_generate(cards, rules.flushes, rules), default=None,
                    key=lambda m: (-sum(c[:2] == rules.wild for c in m.cards), m.power))
        reserved = set(flush.cards) if flush else set()
        if reserved:
            cards.sort(key=reserved.__contains__)
        legal = list(_generate(cards, patterns, rules))
        counts = Counter(c[0] for c in hand)
        rocket = counts[15] == counts[16] == 2
        def preference(m):
            used = Counter(c[0] for c in m.cards)
            fragmented = sum(n < counts[r] for r, n in used.items())
            broken = any(n < counts[r] and counts[r] >= 4 for r, n in used.items())
            bomb = m.kind in _BOMBS
            wild = sum(c[:2] == rules.wild for c in m.cards)
            waste_flush = bool(reserved and not reserved.isdisjoint(m.cards) and
                               m.kind != 'straight_flush')
            broken = broken or (rocket and max(used) >= 15 and m.kind != 'joker_bomb')
            return (len(m.cards) != len(hand), broken or waste_flush, bomb,
                    _tier(m.kind, len(m.cards)) if bomb else -len(m.cards),
                    wild, fragmented, m.power, sum(rules.power[r] * n for r, n in used.items()))
        legal.sort(key=preference)
        if top:
            partner_up = self.owner == (self.turn + 2) % 4
            danger = any(0 < len(self.hands[i]) <= 3 for i in range(4) if (i - self.turn) % 2)
            def play_before_pass(m):
                return len(m.cards) == len(hand) or (not partner_up and
                                                     (danger or m.kind not in _BOMBS))
            yes, no = [], []
            for m in legal:
                (yes if play_before_pass(m) else no).append(m)
            return yes + [None] + no
        return legal

    choose_ai_move = Game.bot_move
