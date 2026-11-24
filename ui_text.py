"""Bilingual display strings. The rules, physical card IDs and match log stay canonical."""
import re

LANGUAGES = ('en', 'zh')
SEATS = {'zh': ('你', '下家', '队友', '上家'),
         'en': ('You', 'Right', 'Partner', 'Left')}

def language(lang):
    if lang not in LANGUAGES:
        raise ValueError(f'Unsupported language: {lang!r}')
    return lang


# UI copy is indexed by its original Chinese spelling. Keep short strings on
# the LCD; full joker names are used in prose, L/H + a crown on the cards.
_EN = {
    '掼蛋': 'GUANDAN', '打': 'Lv.', '出牌：': 'Played: ',
    '本局结算': 'Deal result', '我方赢得整场': 'We win the match', '对方赢得整场': 'They win the match',
    '头游': 'First out', '我方胜': 'Our team wins', '对方胜': 'Their team wins',
    '二游': '2nd', '三游': '3rd', '末游': '4th', '未出完': 'Cards left',
    '我方': 'Us', '对方': 'Them', 'A  新比赛': 'A  New match', 'A  下一局': 'A  Next deal',
    '自由领出': 'Free lead', '过': 'Pass', '上滑选牌': 'Swipe up to select',
    '请先选牌': 'Select cards first', '不能这样出': 'Not a legal play',
    '小王': 'Low Joker', '大王': 'High Joker',
    '首局打2 · 你先出': 'Opening level 2 · You lead',
    '级牌必须为 2 至 A': 'Level must be 2 to A', '点数或张数无效': 'Invalid rank or count',
    '不是合法牌型': 'Invalid combination', '本局已结束': 'Deal is over',
    '领出不能过牌': 'Cannot pass on a lead', '必须压过桌面牌': 'Must beat the last play',
    '所选牌不在手中': 'Cards not in hand', '牌局尚未结束': 'Deal is not over',
    '结算后才能开下一局': 'Finish this deal first', '不能选这张贡牌': 'Not an eligible tribute card',
}
_EN.update(zip(SEATS['zh'], SEATS['en']))


def ui(lang, key):
    return _EN[key] if lang == 'en' else key


def face(rank, lang, short=False):
    if rank in (15, 16):
        if short:
            return (('L', 'H') if lang == 'en' else ('小', '大'))[rank - 15]
        return ui(lang, ('小王', '大王')[rank - 15])
    return {11: 'J', 12: 'Q', 13: 'K', 14: 'A'}.get(rank, str(rank))


_KINDS = {'single': 'Single', 'pair': 'Pair', 'triple': 'Triple', 'house': 'Full house',
          'straight': 'Straight', 'pair_run': 'Pair run', 'triple_run': 'Triple run',
          'straight_flush': 'Straight flush', 'joker_bomb': 'Four jokers'}


def move_label(move, lang):
    if lang == 'zh':
        return move.label
    kind = move.kind
    if kind == 'joker_bomb':
        return _KINDS[kind]
    a, b = face(move.ranks[0], lang), face(move.ranks[-1], lang)
    if kind == 'bomb':
        return f'{len(move.cards)}-card bomb {a}'
    if kind == 'house':
        detail = f'{a} over {b}'
    elif kind in ('straight', 'pair_run', 'triple_run', 'straight_flush'):
        detail = f'{move.suit or ""}{a}–{b}'
    else:
        detail = a
    return f'{_KINDS[kind]} {detail}'


# matchplay exposes canonical strings, including delayed notices copied to
# Table.notice. Match the full message grammar rather than replacing Chinese
# substrings out of context (in particular 队友 as a seat vs. head's partner).
_SEAT = '(' + '|'.join(SEATS['zh']) + ')'
_GIFT = re.compile(r'(单贡|双贡) · ' + _SEAT + '选贡牌')
_BACK = re.compile(_SEAT + '收(.+) · 还贡给' + _SEAT)
_LEAD = re.compile('(抗贡|同贡顺时针|还贡完毕) · ' + _SEAT + '先出')
_RESULT = re.compile('头游：' + _SEAT + r' · 队友第([234]) · (我方|对方)(.+)')


def message(value, lang):
    if lang == 'zh' or not value:
        return value
    if value in _EN:
        return _EN[value]
    if m := _GIFT.fullmatch(value):
        kind, actor = m.groups()
        kind = 'Single' if kind == '单贡' else 'Double'
        return f'{kind} tribute · {_EN[actor]} to give'
    if m := _BACK.fullmatch(value):
        actor, card, payer = m.groups()
        return f'{_EN[actor]} got {_EN.get(card, card)} · Return to {_EN[payer]}'
    if m := _LEAD.fullmatch(value):
        note, actor = m.groups()
        note = {'抗贡': 'Tribute resisted', '同贡顺时针': 'Tribute tied (clockwise)',
                '还贡完毕': 'Tribute complete'}[note]
        return f'{note} · {_EN[actor]} to lead'
    if m := _RESULT.fullmatch(value):
        head, place, team, status = m.groups()
        place = {'2': '2nd', '3': '3rd', '4': '4th'}[place]
        status = {'过A夺冠': 'cleared A', '留A再战': 'stay at A'}.get(
            status, status.strip().replace('（下局打A）', ' (next: A)'))
        partner = SEATS['en'][SEATS['zh'].index(head) ^ 2]
        return f'First: {_EN[head]} · {partner} {place} · {_EN[team]}: {status}'
    return value  # caller-supplied / already localized notice
