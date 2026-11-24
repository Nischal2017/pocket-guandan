"""Partnership match and next-deal tribute for PhysicalGame (clockwise seats 0..3).

House rules: tied double tribute goes to the head from the first payer
clockwise from the head; that payer leads. If no ordinary 2..10 can be
returned, give a weakest non-wild from the original hand. An unsuccessful
A attempt stays at A indefinitely (no three-strikes demotion).
"""
import random

from guandan import PhysicalGame


_SEATS = ('你', '下家', '队友', '上家')
_TEAMS = ('我方', '对方')


def _face(rank):
    return {11: 'J', 12: 'Q', 13: 'K', 14: 'A', 15: '小王', 16: '大王'}.get(rank, str(rank))


def _label(card):
    rank, suit, _ = card
    return (suit if rank < 15 else '') + _face(rank)


def _nonwild(hand, level):
    return [c for c in hand if c[:2] != (level, '♥')]


class Match:
    def __init__(self, seed=None):
        self._rng = random.Random(seed)
        self.levels = [2, 2]
        self.banker = 0
        self.game = PhysicalGame(seed, level=2)
        self.phase = 'play'
        self.champion = None
        self.summary = ''
        self.message = '首局打2 · 你先出'
        self.resisted = False
        self.tribute_kind = None
        self._head = None
        self._payers = ()
        self._queue = []

    @property
    def actor(self):
        if self.phase == 'tribute':
            return self._queue[0]
        if self.phase == 'play' and not self.game.over:
            return self.game.turn
        return None

    def settle(self):
        """Settle once. The finish list may contain synthetic trailing seats."""
        if self.phase in ('result', 'match_over'):
            return self.summary
        if self.phase != 'play' or not self.game.over:
            raise ValueError('牌局尚未结束')
        actual = [s for s in self.game.finish if not self.game.hands[s]]
        live = [s for s, h in enumerate(self.game.hands) if h]
        head = self._head = actual[0]
        partner, team = head ^ 2, head % 2
        if len(live) == 2:
            # Both losers still hold cards: they are unranked, not 3rd/4th.
            place = 2
            self._payers = tuple(sorted(live, key=lambda s: (s - head) % 4))
        else:
            (last,) = live
            place = 4 if last == partner else 3
            self._payers = (last,)
        before = self.levels[team]
        graduated = self.banker == team and self.game.level == before == 14 and place != 4
        self.levels[team] = min(14, before + 5 - place)
        self.banker = team
        after = self.levels[team]
        status = f'{_TEAMS[team]} {_face(before)}→{_face(after)}'
        if graduated:
            self.champion = team
            status = f'{_TEAMS[team]}过A夺冠'
        elif before == 14:
            status = f'{_TEAMS[team]}留A再战'
        elif after == 14:
            status += '（下局打A）'
        self.summary = f'头游：{_SEATS[head]} · 队友第{place} · {status}'
        self.message = self.summary
        self.phase = 'match_over' if graduated else 'result'
        return self.summary

    def advance(self):
        if self.phase != 'result':
            raise ValueError('结算后才能开下一局')
        level = self.levels[self.banker]
        self.game = PhysicalGame(self._rng.getrandbits(128), level=level)
        self._queue = list(self._payers)
        self._gifts = {}
        self._returns = {}
        self._source = {}
        self.resisted = sum(c[0] == 16 for s in self._payers for c in self.game.hands[s]) == 2
        if self.resisted:
            self._start_play(self._head, '抗贡')
        else:
            self.phase = 'tribute'
            self.tribute_kind = 'gift'
            self._prompt()

    def _prompt(self):
        actor = self.actor
        if self.tribute_kind == 'gift':
            kind = '双贡' if len(self._payers) == 2 else '单贡'
            self.message = f'{kind} · {_SEATS[actor]}选贡牌'
        else:
            source = self._source[actor]
            self.message = f'{_SEATS[actor]}收{_label(self._gifts[source])} · 还贡给{_SEATS[source]}'

    def eligible(self):
        if self.phase != 'tribute':
            return []
        level = self.game.level
        pool = _nonwild(self.game.hands[self.actor], level)
        if self.tribute_kind == 'gift':
            strength = max(self.game.card_power(c) for c in pool)
        else:
            low = [c for c in pool if c[0] <= 10 and c[0] != level]
            if low:
                return sorted(low)
            strength = min(self.game.card_power(c) for c in pool)
        return [c for c in pool if self.game.card_power(c) == strength]

    def give(self, card):
        """Reserve an exact physical card. Commit all exchanges together."""
        if card not in self.eligible():
            raise ValueError('不能选这张贡牌')
        seat = self._queue.pop(0)
        if self.tribute_kind == 'gift':
            self._gifts[seat] = card
            if not self._queue:
                # Stable sort keeps clockwise payer order when ranks tie.
                ordered = sorted(self._payers, key=lambda s: -self.game.card_power(self._gifts[s]))
                self._queue = [self._head, self._head ^ 2][:len(ordered)]
                self._source = dict(zip(self._queue, ordered))
                self.tribute_kind = 'return'
        else:
            self._returns[seat] = card
            if not self._queue:
                self._exchange()
                return
        self._prompt()

    def _exchange(self):
        hands = self.game.hands
        for recipient, payer in self._source.items():
            gift, back = self._gifts[payer], self._returns[recipient]
            hands[payer][hands[payer].index(gift)] = back
            hands[recipient][hands[recipient].index(back)] = gift
        for h in hands:
            h.sort(key=self.game.card_sort_key)
        tie = len(self._gifts) == 2 and len({c[0] for c in self._gifts.values()}) == 1
        self._start_play(self._source[self._head], '同贡顺时针' if tie else '还贡完毕')

    def _start_play(self, leader, note):
        self._queue = []
        self.tribute_kind = None
        self.game.turn = leader
        self.phase = 'play'
        self.message = f'{note} · {_SEATS[leader]}先出'

    def auto(self):
        if self.phase == 'tribute':
            self.give(self.eligible()[0])
