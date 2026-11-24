import unittest
from pocket import Table

class StackedHand(unittest.TestCase):
    def setUp(self): self.t=Table(0); self.t.focus(True); self.at=0
    def send(self,*codes):
        for code in codes:
            self.at+=.5;self.t.input(code,self.at)
    def test_pair_fast_add_undo(self):
        t=self.t;g=t.piles()[0];self.assertEqual(len(g),3)
        self.send(5,5);self.assertEqual(t.choice().kind,'pair');self.assertEqual(len(t.selected),2)
        self.send(6);self.assertEqual(t.selected,{t.hand[g[0]][2]});self.send(5,1,2);self.assertEqual(t.game.top.kind,'pair')
    def test_suit_and_other_piles(self):
        t=self.t;self.send(9,5);self.assertEqual(t.selected,{t.hand[1][2]});self.send(8,5);self.assertEqual(len(t.selected),2)
        self.send(7,6);self.assertEqual(len(t.selected),1);self.send(7);self.assertEqual(t.hand[t.cursor][:2],(2,'♥'))
    def test_suit_and_wild_meaning_independent(self):
        t=self.t
        for rank in (7,8):
            while t.hand[t.cursor][0]!=rank:self.send(8)
            self.send(5,5)
        while t.hand[t.cursor][:2]!=(2,'♥'):self.send(8)
        self.send(5);self.assertEqual(t.alternatives,2);first=t.choice()
        self.send(9);self.assertEqual(t.choice(),first)
        self.send(1);self.at+=.3;self.send(2);second=t.choice();self.assertNotEqual(first,second)
        self.send(1,2);self.assertEqual(t.game.top,second)
    def test_focus_and_duplicate_event(self):
        t=self.t;t.input(3,1);t.input(4,1.1);t.input(9,1.2);self.assertEqual(t.cursor,1)
        t.focus(False);self.send(5,5,1,2);self.assertFalse(t.selected);self.assertIsNone(t.game.top)
    def test_deck_layout(self):
        t=self.t
        for seed in range(70):
            t.reset(seed)
            groups=t.piles();self.assertEqual(sorted(i for g in groups for i in g),list(range(27)))
            for g in groups:self.assertEqual(len({(t.hand[i][0],t.hand[i][:2]==(t.game.level,'♥')) for i in g}),1)
            for g in groups:
                t.cursor=g[0];t.cache=None;self.assertEqual(t.frame()[215*50:],b'\xff'*1250)

if __name__=='__main__':unittest.main()
