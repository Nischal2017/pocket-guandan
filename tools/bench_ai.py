#!/usr/bin/env python3
"""Compare Hard and Classic on independent, duplicate physical-card deals."""
import argparse
from collections import Counter
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from guandan import PhysicalGame


# Step by six to sample low, mid and high levels even in short runs. A block
# of 52 consecutive seeds covers every (level, first seat) combination once.
def setup(seed):
    return 2 + 6 * seed % 13, seed % 4


def play_round(seed, level, leader, hard_parity, times):
    g = PhysicalGame(seed=seed, level=level)
    g.turn = leader
    while not g.over:
        seat = g.turn
        hard = seat % 2 == hard_parity
        policy = 'hard' if hard else 'classic'
        start = perf_counter() if times is not None else None
        try:
            move = g.bot_move(policy)
            if times is not None:
                times[policy] += perf_counter() - start
                times[policy + '_calls'] += 1
            g.play(move)  # validates pass, ownership, declaration and strength
        except Exception as exc:
            raise RuntimeError(
                f'seed={seed} level={level} leader={leader} '
                f'hard_parity={hard_parity} seat={seat} policy={policy}'
            ) from exc

    # A hand ends when *either* partnership is out. That need not be the
    # head finisher's partnership. Only the unplayed losers of a 1-2 sweep
    # are tied, so the head finisher's partner always has a meaningful place.
    head = g.finish[0]
    partner_place = 1 + g.finish.index(head ^ 2)
    return ('hard' if head % 2 == hard_parity else 'classic'), partner_place


def compare(deals, first_seed, timing=False, verbose=False):
    places = {'hard': Counter(), 'classic': Counter()}
    paired = Counter()
    times = Counter() if timing else None
    for seed in range(first_seed, first_seed + deals):
        level, leader = setup(seed)
        hard_wins = 0
        for parity in (0, 1):
            winner, place = play_round(seed, level, leader, parity, times)
            places[winner][place] += 1
            hard_wins += winner == 'hard'
            if verbose:
                print(f'seed={seed} level={level} leader={leader} '
                      f'hard_parity={parity} head={winner} partner_place={place}')
        paired[hard_wins] += 1

    rounds = deals * 2
    print(f'Deal seeds {first_seed}..{first_seed + deals - 1}; '
          f'{deals} matched pairs, {rounds} rounds (no tribute).')
    print('Policy   Head-outs           1-2 sweeps   1-3   1-4   Advancement points*')
    for policy, counts in places.items():
        heads = sum(counts.values())
        points = 3 * counts[2] + 2 * counts[3] + counts[4]
        print(f'{policy:7}  {heads:5}/{rounds} ({heads / rounds:5.1%})'
              f'  {counts[2]:10} {counts[3]:5} {counts[4]:5} {points:20}')
    print('*Uncapped 3/2/1 points for head + partner finishing 2nd/3rd/4th; '
          'not a simulated match through A.')
    print(f'Paired head-outs: Hard won both {paired[2]}, split {paired[1]}, '
          f'Classic won both {paired[0]}.')
    if times is not None:
        for policy in places:
            calls = times[policy + '_calls']
            print(f'{policy} decision time: {times[policy]:.3f}s for {calls} turns '
                  f'({1000 * times[policy] / calls:.2f} ms/turn)')


def main():
    parser = argparse.ArgumentParser(description=(
        'Replay each seeded deal with the same hands, level and first seat; '
        'swap Hard and Classic partnerships. Every 52 seeds cover levels 2-A '
        'and all four first seats. Each team leads once per pair.'
    ))
    parser.add_argument('--deals', type=int, default=52, metavar='N',
                        help='number of unique deals; each plays twice (default: 52)')
    parser.add_argument('--seed', type=int, default=0, metavar='S',
                        help='first nonnegative deal seed (default: 0)')
    parser.add_argument('--timing', action='store_true',
                        help='also report wall-clock decision times (not deterministic)')
    parser.add_argument('--verbose', action='store_true', help='print each round result')
    args = parser.parse_args()
    if args.deals < 1 or args.seed < 0:
        parser.error('--deals must be positive and --seed must be nonnegative')
    compare(args.deals, args.seed, args.timing, args.verbose)


if __name__ == '__main__':
    main()
