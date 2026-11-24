"""Hard must be legal, deterministic, and blind to other players' cards."""
import unittest
from unittest.mock import patch
from guandan import PhysicalGame, interpretations
from lcd_app import parse_args
from pocket import Table


class CountOnly:
    def __init__(self, n): self.n = n
    def __len__(self): return self.n
    def __iter__(self): raise AssertionError('read hidden cards')
    def __getitem__(self, key): raise AssertionError('read hidden cards')


class HardMode(unittest.TestCase):
    def test_access_boundary_and_determinism(self):
        for level in (2, 7, 14):
            g = PhysicalGame(0,level)
            choice = g.bot_move('hard')
            self.assertIn(choice,g.options())
            g.hands[1:] = [CountOnly(n) for n in (12, 19, 23)]
            self.assertEqual(g.bot_move('hard'),choice)
            with patch('hardbot.choose',return_value=choice) as spy:
                g.bot_move('hard')
                self.assertEqual(spy.call_args.args[-1],(11,11,11,11))

    def test_mode_and_teammate(self):
        self.assertEqual(parse_args([]).difficulty,'hard')
        for mode in ('hard','classic'):
            t = Table(17,difficulty=mode); t.focus(True)
            for seat in (1,2,3):
                t.game.turn=seat; t.until=0
                m=t.game.bot_move('classic')
                with patch.object(t.game,'bot_move',return_value=m) as bot, patch.object(t,'play'):
                    t.tick();bot.assert_called_once_with(mode if seat%2 else 'classic')
            t.reset(18);self.assertEqual(t.difficulty,mode)
        with self.assertRaises(ValueError): Table(difficulty='typo')

    def test_can_go_out_over_partner(self):
        g=PhysicalGame(2);g.owner=2
        g.top=interpretations([(3,'♣',99)])[0]
        g.hands[0]=[(7,'♣',1)]
        self.assertEqual(g.bot_move('hard').ranks,(7,))

    def test_complete_legal_deals(self):
        for seed,level in enumerate((2,4,8,14)):
            g=PhysicalGame(seed,level);g.turn=seed%4
            for _ in range(432):
                if g.over:break
                g.play(g.bot_move('hard' if g.turn%2 else 'classic'))
            self.assertTrue(g.over)
