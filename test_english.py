"""Exercise actual LCD frames and the text sent to Cairo, with no device window."""
import contextlib
import io
import unittest
from unittest.mock import patch

from guandan import PhysicalGame, interpretations
from hand_view import render, _TYPE
from ink import Canvas
from lcd_app import parse_args
from pocket import Table
from ui_text import face, message, move_label


class EnglishDisplay(unittest.TestCase):
    def screen(self, table, lang):
        labels = []
        draw = Canvas.text

        def record(canvas, x, y, value, *args, **kwargs):
            labels.append(value)
            return draw(canvas, x, y, value, *args, **kwargs)

        with patch.object(Canvas, 'text', record):
            frame = render(table, lang)
        self.assertEqual(len(frame), 12000)
        self.assertEqual(frame[215*50:], b'\xff' * 1250)
        if lang == 'en':
            self.assertNotRegex(' '.join(labels), r'[\u3400-\u9fff，：（）]')
        return labels

    def test_language_selection_and_first_frame(self):
        t = Table(0)
        self.assertEqual(parse_args([]).lang, 'en')
        args = parse_args(['--lang', 'zh', '--opening-seed', '2'])
        self.assertEqual((args.lang, args.opening_seed), ('zh', 2))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_args(['--lang', 'xx'])
        self.assertEqual(t.frame(), render(t, 'en'))
        zh = Table(0, lang='zh')
        self.assertEqual(zh.frame(), render(t, 'zh'))
        self.assertNotEqual(t.frame(), zh.frame())
        self.assertEqual(t.game.hands, zh.game.hands)
        zh.reset(1)
        self.assertEqual(zh.lang, 'zh')
        self.assertIn('GUANDAN', self.screen(t, 'en'))
        self.assertIn('掼蛋', self.screen(t, 'zh'))

    def test_control_feedback_and_wild_declaration(self):
        t = Table(0)
        t.focus(True)
        t.input(1, 0); t.input(2, 0.1)
        self.assertIn('Select cards first', self.screen(t, 'en'))
        self.assertIn('请先选牌', self.screen(t, 'zh'))
        for rank in (7, 8):
            group = next(g for g in t.piles() if t.hand[g[0]][0] == rank)
            t.cursor = group[0]
            t.pile_gesture(5); t.pile_gesture(5)
        t.cursor = t.piles()[-1][0]
        t.input(5, 1)
        self.assertEqual(t.alternatives, 2)
        self.assertIn('Full house 7 over 8   1/2', self.screen(t, 'en'))
        t.input(1, 2); t.input(2, 3)
        self.assertIn('Full house 8 over 7   2/2', self.screen(t, 'en'))
        t.input(1, 4); t.input(2, 4.1)
        labels = self.screen(t, 'en')
        self.assertIn('Full house 8 over 7', labels)
        self.assertIn('Played: You', labels)
        self.assertIn('三带二 8带7', self.screen(t, 'zh'))
        self.assertNotIn('GUANDAN', labels)

    def test_physical_jokers_and_move_labels(self):
        for rank, mark, name in [(15, 'L', 'Low Joker'), (16, 'H', 'High Joker')]:
            self.assertEqual(face(rank, 'en', short=True), mark)
            self.assertIn(mark, _TYPE)
            m, = interpretations([(rank, '王', 0)])
            self.assertEqual(move_label(m, 'en'), 'Single ' + name)
            self.assertEqual(move_label(m, 'zh'), m.label)
        g = PhysicalGame(11)
        deck = [c for hand in g.hands for c in hand]
        jokers = [c for c in deck if c[0] > 14]
        moves = [*interpretations(jokers), *interpretations([c for c in deck if c[0] == 5][:6])]
        suited = [next(c for c in deck if c[:2] == (r, '♠')) for r in range(10, 15)]
        moves.extend(interpretations(suited))
        self.assertEqual([move_label(m, 'en') for m in moves],
                         ['Four jokers', '6-card bomb 5', 'Straight 10–A', 'Straight flush ♠10–A'])

    def test_deal_results_and_exchange(self):
        for seed, notice in [(0, 'Tribute resisted'), (3, 'Tribute complete'), (4, 'Tribute complete')]:
            t = Table(seed)
            t.focus(True)
            while not t.game.over:
                t.play(t.game.bot_move())
            self.assertIn('Deal result', self.screen(t, 'en'))
            self.assertIn(t.match.summary, self.screen(t, 'zh'))
            t.next_deal()
            while t.match.phase == 'tribute':
                self.assertIn(t.match.message, self.screen(t, 'zh'))
                if t.match.actor == 0:
                    t.input(1, 1); t.input(2, 1.1)
                    self.assertIn('Swipe up to select', self.screen(t, 'en'))
                    t.input(5, 2)
                labels = self.screen(t, 'en')
                self.assertTrue(any('tribute' in s or 'Return to' in s for s in labels))
                t.tribute_action()
            self.assertTrue(any(notice in s for s in self.screen(t, 'en')))

    def test_match_end_and_special_messages(self):
        for canonical, english in [
            ('不能这样出', 'Not a legal play'),
            ('同贡顺时针 · 下家先出', 'Tribute tied (clockwise) · Right to lead'),
            ('你收小王 · 还贡给下家', 'You got Low Joker · Return to Right'),
            ('下家收♠A · 还贡给队友', 'Right got ♠A · Return to Partner'),
            ('头游：队友 · 队友第4 · 我方留A再战', 'First: Partner · You 4th · Us: stay at A'),
            ('头游：上家 · 队友第3 · 对方 Q→A（下局打A）', 'First: Left · Right 3rd · Them: Q→A (next: A)'),
        ]:
            self.assertEqual(message(canonical, 'en'), english)
            self.assertEqual(message(canonical, 'zh'), canonical)
        t = Table(0)
        t.match.game = PhysicalGame(1, level=14)
        t.match.levels = [14, 5]
        t.game.over = True
        t.game.finish = [0, 2, 1, 3]
        t.game.hands[0] = []; t.game.hands[2] = []
        t.match.settle()
        en = self.screen(t, 'en')
        for caption in ['We win the match', 'Cards left', 'Right · Left', 'A  New match',
                        'First: You · Partner 2nd · Us: cleared A']:
            self.assertIn(caption, en)
        self.assertIn('我方赢得整场', self.screen(t, 'zh'))


if __name__ == '__main__':
    unittest.main()
