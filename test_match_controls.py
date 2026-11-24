"""Exercise physical A/swipe input across the boundary between real deals."""
from unittest import TestCase
from pocket import Table


def key(table,*codes):
    for c in codes:table.input(c,100.)


class MatchControls(TestCase):
    def test_play_result_next_tribute_exchange(self):
        # Try multiple real finishes, including a human tribute and a return.
        actions=set()
        for seed in range(32):
            t=Table(seed);t.focus(True)
            while not t.game.over:t.play(t.game.bot_move())
            self.assertEqual(t.match.phase,'result');old_game=t.game
            levels=t.match.levels[:];self.assertGreater(max(levels),2)
            self.assertEqual(len(t.frame()),12000)
            # Merely pressing, canceling, or switching to the picker does not redeal.
            key(t,1,258,2);self.assertIs(old_game,t.game)
            key(t,1,2);self.assertIsNot(old_game,t.game)
            self.assertEqual(t.game.level,levels[t.match.banker]);self.assertEqual(t.deal,2)
            while t.match.phase=='tribute':
                self.assertEqual(len(t.frame()),12000)
                if t.match.actor!=0:
                    t.until=0;t.tick();continue
                actions.add(t.match.tribute_kind);actor=t.match.actor
                self.assertTrue(t.eligible_ids);key(t,1,2);self.assertEqual(t.match.actor,actor)
                key(t,8,5);self.assertIn(t.tribute_selected,t.eligible_ids)
                key(t,6);self.assertIsNone(t.tribute_selected)
                key(t,7,5,1);t.focus(False);key(t,2);t.until=0;t.tick()
                self.assertEqual(t.match.actor,actor);t.focus(True);key(t,1,2)
            self.assertEqual(t.match.phase,'play');self.assertEqual(list(map(len,t.game.hands)),[27]*4)
            self.assertEqual(len({c[2] for h in t.game.hands for c in h}),108)
            self.assertTrue(t.notice);t.play(t.game.bot_move());self.assertFalse(t.notice)
            if actions=={'gift','return'}:break
        self.assertEqual(actions,{'gift','return'})
