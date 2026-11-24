"""Level-aware physical rules, per-deal isolation, and bot canonicalization."""
from itertools import combinations
import unittest

from guandan import PhysicalGame, interpretations, physical_deck


DECK = physical_deck()


def pick(*faces):
    """Fetch unique cards for (rank, suit) faces, possibly repeated."""
    deck = DECK.copy()
    result = []
    for face in faces:
        card = next(c for c in deck if c[:2] == face)
        result.append(card)
        deck.remove(card)
    return result


def natural(rank, n):
    return [c for c in DECK if c[0] == rank and c[1] != '♥'][:n]


def decl(cards, level, kind):
    return next(m for m in interpretations(cards, level) if m.kind == kind)


class LevelRulesTests(unittest.TestCase):
    def test_order_at_every_level(self):
        for level in range(2, 15):
            with self.subTest(level=level):
                order = [r for r in range(2, 15) if r != level] + [level, 15, 16]
                g = PhysicalGame(1, level=level)
                self.assertEqual(g.level, level)
                for hand in g.hands:
                    self.assertEqual(hand, sorted(hand, key=lambda c: (order.index(c[0]), *c[1:])))
                for n, kind in enumerate(('single', 'pair', 'triple', 'bomb'), 1):
                    moves = [decl(natural(r, n), level, kind) for r in order
                             if n <= 2 or r < 15]
                    for weak, strong in zip(moves, moves[1:]):
                        self.assertTrue(strong.beats(weak))
                        self.assertFalse(weak.beats(strong))
                houses = [decl(natural(r, 3) + natural(15, 2), level, 'house')
                          for r in order[:-2]]
                self.assertTrue(all(b.beats(a) for a, b in zip(houses, houses[1:])))

    def test_wild_and_ordinary_hearts(self):
        for level in range(2, 15):
            with self.subTest(level=level):
                wilds = pick((level, '♥'), (level, '♥'))
                for n in (1, 2):
                    moves = interpretations(wilds[:n], level)
                    self.assertEqual([m.ranks for m in moves], [(level,) * n])
                self.assertEqual(interpretations(wilds[:1] + natural(15, 1), level), [])
                other = 3 if level == 2 else 2
                m = decl(wilds[:1] + pick((other, '♥')), level, 'pair')
                face = {11:'J', 12:'Q', 13:'K', 14:'A'}.get(level, str(level))
                self.assertIn(f'♥{face}→{other}', m.description)
                self.assertEqual(interpretations(pick((other, '♥'), (4, '♣')), level), [])
                ten = wilds + [c for c in DECK if c[0] == other]
                self.assertEqual(decl(ten, level, 'bomb').ranks, (other,) * 10)

    def test_natural_runs_and_flush_declarations(self):
        for level in (2, 3, 7, 14):
            for kind, width, copies in [('straight', 5, 1), ('pair_run', 3, 2),
                                        ('triple_run', 2, 3)]:
                moves = []
                for start in range(1, 16 - width):
                    ranks = [14 if r == 1 else r for r in range(start, start + width)]
                    cards = [c for r in ranks for c in natural(r, copies)]
                    m = decl(cards, level, kind)
                    self.assertEqual(m.ranks, tuple(r for r in ranks for _ in range(copies)))
                    moves.append(m)
                self.assertTrue(all(b.beats(a) for a, b in zip(moves, moves[1:])))
        hand = pick((2, '♦'), (3, '♦'), (4, '♦'), (5, '♦'), (14, '♥'))
        flushes = [m for m in interpretations(hand, 14) if m.kind == 'straight_flush']
        self.assertEqual({m.power for m in flushes}, {1, 2})
        self.assertEqual({m.description.split()[-1] for m in flushes}, {'♥A→♦A', '♥A→♦6'})

    def test_reply_cache_isolation_and_play_validation(self):
        for level in (5, 2, 12, 5):
            g = PhysicalGame(0, level)
            g.top = decl(natural(14, 1), level, 'single')
            g.owner = 1
            g.hands[0] = pick((2, '♣'), (5, '♣'), (12, '♣'))
            reply, = (m for m in g.options() if m is not None)
            self.assertEqual(reply.ranks, (level,))
            self.assertEqual(g.choose_ai_move(), reply)
            self.assertEqual(g.legal_interpretations(reply.cards), [reply])
            wrong = decl(reply.cards, 3, 'single')
            with self.assertRaises(ValueError):
                g.play(wrong)
            g.play(reply)
            self.assertEqual(g.top, reply)

    def test_bot_representatives_match_exact_selections(self):
        # An ambiguous wild hand with a flush to reserve. AI can choose a
        # different physical copy, but every declaration must still replay.
        g = PhysicalGame(3, 11)
        hand = g.hands[0] = pick((11, '♥'), (11, '♥'), (2, '♦'), (2, '♥'),
                                 (3, '♦'), (4, '♦'), (5, '♦'), (6, '♦'))
        def key(m):
            return m.kind, m.power, m.ranks, m.suit
        expected = {key(m) for n in range(1, len(hand) + 1) for subset in combinations(hand, n)
                    for m in interpretations(subset, 11)}
        options = g.options()
        self.assertEqual(len(options), len(expected))
        self.assertEqual({key(m) for m in options}, expected)
        for m in options:
            self.assertIn(m, g.legal_interpretations(reversed(m.cards)))

    def test_invalid_level(self):
        for level in (1, 15, 'Q', 2.0, True):
            with self.assertRaises(ValueError):
                PhysicalGame(level=level)
            with self.assertRaises(ValueError):
                interpretations([], level)


if __name__ == '__main__':
    unittest.main()
