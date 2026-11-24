"""Deterministic, public-information hand-shape heuristic for Hard opponents.

Scores legal physical plays by the groups left behind. This is a bounded
estimate, not a solver: suit and wildcard legality stay in PhysicalGame.
"""
from collections import Counter
from functools import lru_cache

BOMBS = {'bomb', 'joker_bomb', 'straight_flush'}
# Ranks are stored in 2..A, small joker, big joker order. Runs begin at
# ace-low or 2.., never wrap K-A-2, and never include either joker.
RUNS = tuple((copies, tuple(tuple((i - 1) % 13 for i in range(start, start + width))
                           for start in range(15 - width)))
             for copies, width in ((1, 5), (2, 3), (3, 2)))


def group_cost(counts):
    sizes = Counter(counts)
    # Each rank is a group; matching a triple and a pair removes a lead.
    # Prefer intact bombs and avoid ending the deal with isolated singles.
    return (sum(n > 0 for n in counts) - min(sizes[3], sizes[2])
            - .4 * sum(n >= 4 for n in counts) + .18 * sizes[1])


@lru_cache(maxsize=24000)
def shape(counts):
    best = group_cost(counts)
    for copies, windows in RUNS:
        remaining = list(counts)
        used = 0
        for ranks in windows:
            if all(remaining[r] >= copies for r in ranks):
                for r in ranks:
                    remaining[r] -= copies
                used += 1
                best = min(best, used + group_cost(remaining))
    return best


def choose(hand, options, level, seat, owner, top, public_counts):
    """Only own cards, legal candidates, table play and displayed counts enter."""
    moves = [m for m in options if m is not None]
    if not moves:
        return None
    for m in moves:
        if len(m.cards) == len(hand):
            return m
    if owner == (seat + 2) % 4:
        return None  # Let partner hold the trick unless we could actually go out.
    counts = Counter(c[0] for c in hand)
    danger = min((public_counts[i] for i in ((seat+1)%4, (seat+3)%4)
                  if public_counts[i]), default=11)
    partner = public_counts[(seat+2)%4]

    def cost(m):
        used = Counter(c[0] for c in m.cards)
        score = shape(tuple(counts[r] - used[r] for r in range(2,17)))
        bomb = m.kind in BOMBS
        if bomb:
            score += .25 if score <= 1.3 or danger <= 3 else 1.4
        score += .45 * sum(c[:2] == (level, '♥') for c in m.cards)
        score += .48 * sum(0 < used[r] < counts[r] and counts[r] >= 4 for r in used)
        score += (.02 if bomb else .055) * m.power
        # Avoid handing an opponent a cheap last single/pair. When leading,
        # give a nearly-out partner an affordable play of their hand size.
        if danger <= 2 and len(m.cards) == danger:
            score += 1.7 - .14 * m.power
        if top is None and 0 < partner <= 2 and len(m.cards) == partner:
            score -= max(0, .8 - .11 * m.power)
        if top and danger <= 3 and public_counts[owner] <= 3 and not bomb:
            score -= .07 * m.power
        return score

    best = min(moves, key=cost)
    if top and best.kind in BOMBS and danger > 3 and len(hand)-len(best.cards) > 4:
        return None
    return best
