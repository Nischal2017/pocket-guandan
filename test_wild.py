"""Physical-card engine regression and independent small-hand oracle tests."""
from collections import Counter
from dataclasses import replace
from itertools import combinations, product
import unittest

from guandan import Game, Move, PhysicalGame, SUITS, interpretations, physical_deck


def cards(*ranks):
    """Give each rank ordinary physical copies, or a ♥2 for 'W'."""
    deck = physical_deck()
    out = []
    for r in ranks:
        if r == 'W':
            c = next(c for c in deck if c[:2] == (2, '♥'))
        else:
            c = next(c for c in deck if c[0] == r and c[:2] != (2, '♥'))
        deck.remove(c)
        out.append(c)
    return out


def declaration(hand, kind):
    return next(m for m in interpretations(hand) if m.kind == kind)


class PhysicalRules(unittest.TestCase):
    def test_deck(self):
        a, b, c = (PhysicalGame(seed).hands for seed in (67, 67, 68))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual([len(h) for h in a], [27] * 4)
        deck = sum(a, [])
        self.assertEqual(len({i for _, _, i in deck}), 108)
        self.assertEqual(Counter(c[:2] for c in deck),
                         {(r, s): 2 for r in range(2, 17) for s in (SUITS if r <= 14 else ('王',))})

    def test_wild_groups(self):
        for selection, expected in [(['W'], [('single', (2,))]),
                                    (['W', 'W'], [('pair', (2, 2))]),
                                    ([5, 'W', 'W'], [('triple', (5,) * 3)]),
                                    ([15, 'W'], []), ([16, 16, 'W'], []),
                                    ([15, 16, 'W', 'W'], [])]:
            self.assertEqual([(m.kind, m.ranks) for m in interpretations(cards(*selection))], expected)
        pair = declaration(cards(9, 'W'), 'pair')
        self.assertIn('♥2→9', pair.description)
        self.assertEqual(declaration(cards(8, 8, 'W', 15, 15), 'house').ranks, (8, 8, 8, 15, 15))

    def test_runs_and_ambiguous_declarations(self):
        suit = '♦'
        hand = [(r, suit, r) for r in (4, 5, 6, 7)] + cards('W')
        moves = interpretations(hand)
        self.assertEqual({(m.kind, m.power) for m in moves},
                         set(product(('straight', 'straight_flush'), (3, 4))))
        self.assertEqual(len({m.label for m in moves}), 4)
        for m in moves:
            self.assertCountEqual(m.cards, hand)
            self.assertEqual(m.suit, suit if m.kind == 'straight_flush' else None)
            for c, r in zip(m.cards, m.ranks):
                if c[:2] != (2, '♥'):
                    self.assertEqual(c[0], r)
        for kind, hand in [('straight', cards(14, 2, 3, 'W', 5)),
                           ('straight', cards(10, 'W', 12, 13, 14)),
                           ('pair_run', cards(9, 9, 'W', 10, 11, 'W')),
                           ('triple_run', cards(14, 14, 'W', 2, 2, 'W'))]:
            self.assertIn(kind, [m.kind for m in interpretations(hand)])
        self.assertEqual(interpretations(cards(13, 14, 'W', 3, 4)), [])
        moves = interpretations(cards(3, 3, 4, 4, 'W'))
        self.assertEqual({m.ranks for m in moves}, {(3, 3, 3, 4, 4), (4, 4, 4, 3, 3)})
        moves = interpretations(cards(5, 5, 5, 'W', 'W'))
        self.assertEqual({m.kind for m in moves}, {'bomb', 'house'})
        self.assertEqual({m.ranks[-1] for m in moves if m.kind == 'house'}, set(range(2, 15)) - {5})

    def test_hierarchy_and_no_suit_tiebreak(self):
        sf = declaration([(r, '♠', r) for r in range(8, 13)], 'straight_flush')
        other = declaration([(r, '♦', r) for r in range(8, 13)], 'straight_flush')
        self.assertFalse(sf.beats(other))
        self.assertFalse(other.beats(sf))
        order = [declaration(cards(16, 16), 'pair'), declaration(cards(*[2]*4), 'bomb'),
                 declaration(cards(3, 3, 3, 'W', 'W'), 'bomb'), sf,
                 declaration([(r, '♥', r) for r in range(9, 14)], 'straight_flush'),
                 declaration(cards(*[3]*6), 'bomb'), declaration(cards(*[2]*6), 'bomb'),
                 declaration(cards(*[4]*8, 'W', 'W'), 'bomb'),
                 declaration(cards(15, 16, 15, 16), 'joker_bomb')]
        for i, m in enumerate(order):
            for j, n in enumerate(order):
                self.assertEqual(m.beats(n), i > j)

    def test_invalid_hand_and_forgery(self):
        for hand in [[], [(5, '王', 1)], [(16, '♥', 1)], [(1, '♠', 4)],
                     [(3, '♠', i) for i in range(3)], [(4, '♥', 1), (4, '♠', 1)]]:
            self.assertEqual(interpretations(hand), [])
        g = PhysicalGame(1)
        g.hands[0] = cards(4, 4, 4, 'W', 'W', 7)
        m = declaration(g.hands[0][:5], 'bomb')
        state = list(g.hands[0])
        for bad in [replace(m, power=55), replace(m, kind='joker_bomb'),
                    replace(m, ranks=(16,)*5), declaration(cards(14), 'single')]:
            with self.assertRaises(ValueError):
                g.play(bad)
            self.assertEqual(g.hands[0], state)
        g.play(m)
        self.assertEqual(g.hands[0], state[5:])
        self.assertEqual(g.top, m)

    def test_exact_ids_and_filtering(self):
        g = PhysicalGame(2)
        g.hands[0] = cards(4, 4, 4, 5, 5, 'W')
        select = g.hands[0][1:]   # not the first physical copy
        g.top = declaration(cards(4, 4, 4, 7, 7), 'house')
        legal = g.legal_interpretations(select)
        self.assertEqual([m.ranks for m in legal], [(5, 5, 5, 4, 4)])
        g.play(legal[0])
        self.assertEqual(g.hands[0], cards(4))

    def test_all_subsets_against_rank_substitution_oracle(self):
        # Independent slow oracle, deliberately restricted to a tiny hand.
        # Check ALL manual declarations, then existential completeness of bot
        # representatives (one physical realization per logical pattern).
        hand = cards(14, 2, 3, 3, 4, 5, 'W', 'W')
        all_declarations = set()
        for n in range(1, len(hand)+1):
            for subset in combinations(hand, n):
                fix = [c for c in subset if c[:2] != (2, '♥')]
                nw = len(subset) - len(fix)
                ranks = [c[0] for c in fix]
                suits = {c[1] for c in fix}
                expected = set()
                for assignment in product(range(2, 15) if fix else [2], repeat=nw):
                    try:
                        m = Move((*ranks, *assignment))
                    except ValueError:
                        continue
                    expected.add((m.kind, m.cards, m.power, None))
                    if m.kind == 'straight' and len(suits) == 1:
                        expected.add(('straight_flush', m.cards, m.power, next(iter(suits))))
                actual = {(m.kind, m.ranks, m.power, m.suit) for m in interpretations(subset)}
                self.assertEqual(actual, expected, subset)
                all_declarations |= expected
        g = PhysicalGame(2)
        g.hands[0] = hand
        self.assertEqual({(m.kind, m.ranks, m.power, m.suit) for m in g.options()}, all_declarations)

    def test_bot_preserves_flush_and_partner(self):
        g = PhysicalGame(1)
        flush = [(r, '♠', r) for r in range(4, 9)]
        g.hands[0] = flush + [(4, '♥', 104)]
        g.top = declaration(cards(3), 'single')
        g.owner = 1
        self.assertEqual(g.bot_move().cards, ((4, '♥', 104),))
        g.owner = 2
        self.assertIsNone(g.bot_move())
        g.hands[0] = flush
        self.assertEqual(g.bot_move().kind, 'straight_flush')

    def test_rounds(self):
        for seed in range(32):
            g = PhysicalGame(seed)
            played = set()
            for step in range(432):
                if g.over:
                    break
                m = g.bot_move()
                if m:
                    self.assertIn(m, g.legal_interpretations(m.cards))
                    self.assertTrue(played.isdisjoint(m.cards))
                    played.update(m.cards)
                else:
                    self.assertIsNotNone(g.top)
                g.play(m)
            self.assertTrue(g.over)
            self.assertCountEqual(g.finish, range(4))
            self.assertEqual(len(played) + sum(map(len, g.hands)), 108)


if __name__ == '__main__':
    unittest.main()
