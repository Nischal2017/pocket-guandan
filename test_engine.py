"""Regression tests for the rank-only Guandan round. Run: python3 -m unittest."""
from collections import Counter
import unittest

from guandan import Game, Move


def game_with(*hands):
    game = Game(seed=0)
    game.hands = [list(h) for h in hands]
    return game


class Rules(unittest.TestCase):
    def test_level_and_jokers(self):
        moves = [Move([r]) for r in [3, 4, 14, 2, 15, 16]]
        for small, big in zip(moves, moves[1:]):
            self.assertTrue(big.beats(small))
            self.assertFalse(small.beats(big))
            self.assertFalse(small.beats(small))
        self.assertFalse(Move([3, 3]).beats(moves[-1]))

    def test_jokers_and_bombs(self):
        order = [Move([16, 16]), Move([3]*4), Move([2]*4),
                 Move([3]*5), Move([2]*8), Move([15, 16, 15, 16])]
        for i, m in enumerate(order):
            for j, other in enumerate(order):
                self.assertEqual(m.beats(other), i > j)
        self.assertEqual(order[-1].cards, (15, 15, 16, 16))

    def test_house(self):
        h = Move([16, 3, 3, 16, 3])
        self.assertEqual(h.cards, (3, 3, 3, 16, 16))
        self.assertTrue(Move([4]*3 + [5]*2).beats(h))
        self.assertFalse(h.beats(Move([3]*3 + [4]*2)))

    def test_sequences(self):
        for w, n in [(5, 1), (3, 2), (2, 3)]:
            runs = [Move([14 if r == 1 else r for r in range(i, i+w) for _ in range(n)])
                    for i in range(1, 16-w)]
            self.assertEqual(runs[0].cards[:n], (14,)*n)
            self.assertEqual(runs[-1].cards[-n:], (14,)*n)
            for low, high in zip(runs, runs[1:]):
                self.assertTrue(high.beats(low))
                self.assertFalse(low.beats(high))

    def test_invalid(self):
        for cards in [[], [1], [True], [17], [2]*9, [15]*3, [11,12,13,14,15],
                      [13,14,2,3,4], [2,3,4,5], [3,4,5,6,7,8],
                      [3,3,4,4], [5,5,6,6,8,8], [16,15], [3,3,3,4]]:
            with self.subTest(cards=cards), self.assertRaises(ValueError):
                Move(cards)

    def test_generated_options_exhaustive(self):
        from itertools import combinations
        hand = [14,2,2,3,3,3,3,4,4,5,5,6,15,15,16,16]
        # Exhaust the multiset, not just the engine's templates.
        expected = set()
        for n in range(1, len(hand)+1):
            for cards in set(combinations(hand, n)):
                try:
                    expected.add(Move(cards))
                except ValueError:
                    pass
        opts = game_with(hand, [8], [9], [10]).options()
        self.assertEqual(set(opts), expected)
        self.assertEqual(len(opts), len(expected))


class Round(unittest.TestCase):
    def test_deal_and_seed(self):
        g = Game(42)
        self.assertEqual(g.hands, Game(42).hands)
        self.assertEqual([len(h) for h in g.hands], [27]*4)
        self.assertEqual(Counter(r for h in g.hands for r in h),
                         {r: 8 if r < 15 else 2 for r in range(2,17)})
        self.assertEqual(g.turn, 0)
        self.assertIsNone(g.top)
        self.assertIsNone(g.owner)

    def test_pass_reset_and_reentry(self):
        g = game_with([3,11], [5,6], [4,8], [7,9])
        g.play(Move([3]))
        g.play(None)
        g.play(Move([4]))
        g.play(None)
        g.play(None)
        self.assertEqual(g.turn, 1)
        self.assertIn(Move([5]), g.options())
        g.play(None)
        self.assertEqual(g.turn, 2)
        self.assertIsNone(g.top)
        self.assertIsNone(g.owner)
        self.assertNotIn(None, g.options())

    def test_wind_and_team_completion(self):
        g = game_with([3], [5], [4], [6])
        g.play(Move([3]))
        for _ in range(3):
            g.play(None)
        self.assertEqual(g.turn, 2)
        self.assertEqual(g.finish, [0])
        g.play(Move([4]))
        self.assertTrue(g.over)
        self.assertEqual(g.finish[:2], [0,2])
        self.assertCountEqual(g.finish, range(4))
        self.assertEqual(g.options(), [])
        self.assertIsNone(g.bot_move())
        with self.assertRaises(ValueError):
            g.play(None)

    def test_skip_finished_and_last_place(self):
        g = game_with([3], [4], [8,9], [7])
        g.play(Move([3]))
        g.play(Move([4]))
        g.play(None)
        g.play(None)
        self.assertEqual(g.turn, 3)
        g.play(Move([7]))
        self.assertEqual(g.finish, [0,1,3,2])
        self.assertTrue(g.over)

    def test_bot_respects_partner(self):
        g = game_with([5], [6], [7,8], [9])
        g.play(Move([5]))
        g.play(None)
        self.assertIsNone(g.bot_move())
        self.assertIn(Move([7]), g.options())
        g.hands[2] = [7]
        self.assertEqual(g.bot_move(), Move([7]))

    def test_reject_without_mutating(self):
        g = game_with([4,5], [3,6], [7], [8])
        for action in (None, Move([4,4]), Move([8]), [4]):
            with self.assertRaises(ValueError):
                g.play(action)
        self.assertEqual(g.hands[0], [4,5])
        self.assertEqual(g.turn, 0)
        g.play(Move([4]))
        with self.assertRaises(ValueError):
            g.play(Move([3]))
        self.assertEqual(g.turn, 1)
        self.assertEqual(g.owner, 0)
        self.assertEqual(g.top, Move([4]))

    def test_many_complete_rounds(self):
        for seed in range(64):
            g = Game(seed)
            for _ in range(432):  # <=108 nonpasses, each followed by <=3 passes
                if g.over:
                    break
                self.assertTrue(g.hands[g.turn])
                action = g.bot_move()
                if action is not None:
                    self.assertTrue(action.beats(g.top))
                g.play(action)
            self.assertTrue(g.over, f'seed {seed} never terminated')
            self.assertCountEqual(g.finish, range(4))
            self.assertFalse(g.hands[g.finish[0]])
            self.assertFalse(g.hands[g.finish[1]])


if __name__ == '__main__':
    unittest.main()
