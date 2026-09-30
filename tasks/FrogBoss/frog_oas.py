"""Persistent, outcome-verified weighted voting. Scores are not win probabilities."""
import json
import re
import random
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import cv2
import requests

from tasks.FrogBoss.oas_sources import DASHEN_UIDS


def fingerprint(image):
    # Only the two lineups: excludes countdown, votes, chest and result text.
    bits = []
    for x in (300, 807):
        crop = image[112:233, x:x + 398]
        gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        small = cv2.resize(gray, (33, 8))
        bits.extend((small[:, 1:] > small[:, :-1]).flatten())
    return ''.join('1' if bit else '0' for bit in bits)


def same_lineup(a, b):
    return len(a) == len(b) == 512 and sum(x != y for x, y in zip(a, b)) <= 20


def parse_side(text):
    # Ambiguous text is deliberately excluded rather than guessed by word order.
    red = bool(re.search(r'押红|押左|压红|压左|我红|我左|红优|红方胜|红色胜', text))
    blue = bool(re.search(r'押蓝|押右|压蓝|压右|我蓝|我右|蓝优|蓝方胜|蓝色胜', text))
    if re.search(r'不押|不压|别押|别压|不要押|不要压', text):
        return None
    return ('LEFT' if red else 'RIGHT') if red != blue else None


class OasHistory:
    def __init__(self, path):
        self.path = Path(path)
        self.events = []
        if self.path.exists():
            for line in self.path.read_text(encoding='utf-8').splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue  # Ignore a truncated final record after interruption.
                if isinstance(event, dict):
                    self.events.append(event)

    def append(self, kind, **data):
        event = dict(version=1, kind=kind, recorded_at=datetime.now().isoformat(), **data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Leading newline separates a possible truncated tail from the new event.
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write('\n' + json.dumps(event, ensure_ascii=False) + '\n')
            stream.flush()
        self.events.append(event)
        return event

    def reliability(self, source):
        decisions = {e['id']: e for e in self.events if e.get('kind') == 'decision'}
        correct = total = 0
        seen = set()
        for result in self.events:
            if result.get('kind') != 'result' or result['id'] in seen:
                continue
            seen.add(result['id'])
            vote = decisions.get(result['id'], {}).get('votes', {}).get(source)
            if vote in ('LEFT', 'RIGHT'):
                total += 1
                correct += vote == result['winner']
        # Unverified newcomers start neutral; verified sources use raw win rate.
        return correct / total if total else 0.5

    def settle(self, signature, winner):
        if winner not in ('LEFT', 'RIGHT'):
            return None
        # Include already settled records when checking ambiguity: never transfer
        # an old result to a newer decision with an identical lineup.
        matches = [e for e in self.events if e.get('kind') == 'decision'
                   and same_lineup(e['signature'], signature)]
        if len(matches) != 1:
            self.append('unverified_result', signature=signature, winner=winner,
                        reason='missing_or_ambiguous_decision')
            return None
        decision = matches[0]
        if any(e.get('kind') == 'result' and e['id'] == decision['id'] for e in self.events):
            return None
        return self.append('result', id=decision['id'], winner=winner,
                           outcomes={s: v == winner for s, v in decision['votes'].items()})

    def choose(self, signature, left, right, predictions):
        now = datetime.now()
        # Re-entry in the same slot reuses the original frozen decision.
        slot = f'{now.date()}:{now.hour // 2}'
        for e in reversed(self.events):
            if e.get('kind') == 'decision' and e['slot'] == slot and same_lineup(e['signature'], signature):
                return e
        crowd = ('LEFT' if left > right else 'RIGHT') if left != right and left + right > 0 else None
        votes = {p['uid']: p['side'] for p in predictions if p.get('side') in ('LEFT', 'RIGHT')}
        expert_left = sum(v == 'LEFT' for v in votes.values())
        expert_right = sum(v == 'RIGHT' for v in votes.values())
        expert_side = ('LEFT' if expert_left > expert_right else 'RIGHT') if expert_left != expert_right else None
        if crowd:
            votes['crowd'] = crowd
        cold_start = not any(e.get('kind') == 'result' for e in self.events)
        weights = {} if cold_start else {uid: self.reliability(uid) for uid in votes}
        scores = {'LEFT': 0.0, 'RIGHT': 0.0}
        if cold_start:
            # Two equal votes: the expert majority as a whole and the crowd.
            for vote in (expert_side, crowd):
                if vote:
                    scores[vote] += 1
        else:
            for uid, vote in votes.items():
                scores[vote] += weights[uid]
        tied = abs(scores['LEFT'] - scores['RIGHT']) < 1e-12
        side = random.choice(('LEFT', 'RIGHT')) if tied else max(scores, key=scores.get)
        return self.append('decision', id=uuid4().hex, slot=slot, signature=signature,
                           left=left, right=right, votes=votes, weights=weights,
                           scores=scores, side=side, strategy_version=2,
                           mode='cold_start' if cold_start else 'win_rate',
                           expert_counts={'LEFT': expert_left, 'RIGHT': expert_right},
                           expert_side=expert_side, crowd_side=crowd, random_tiebreak=tied)


def fetch_predictions(history):
    now = datetime.now()
    used = {(e.get('uid'), e.get('feed_id')) for e in history.events
            if e.get('kind') == 'fetch' and e.get('accepted')}
    predictions = []
    with requests.Session() as session:
        for uid in DASHEN_UIDS:
            feed_id = None
            try:
                response = session.get('https://inf.ds.163.com/v1/web/feed/basic/getSomeOneFeeds',
                                       params={'feedTypes': '1,2,3,4,6,7,10,11', 'someOneUid': uid}, timeout=(3, 5))
                response.raise_for_status()
                feeds = response.json().get('result', {}).get('feeds', [])
                if not feeds:
                    history.append('fetch', uid=uid, accepted=False, reason='no_feed')
                    continue
                feed_id = feeds[0]['id']
                response = session.get('https://inf.ds.163.com/v1/web/feed/basic/facade',
                                       params={'feedId': feed_id}, timeout=(3, 5))
                response.raise_for_status()
                feed = response.json()['result']['feed']
                content = feed['content']
                if isinstance(content, str):
                    content = json.loads(content)
                body = content['body']['text']
                raw_time = feed.get('createTime')
                published = None
                try:
                    published = datetime.fromtimestamp(float(raw_time) / 1000)
                except (TypeError, ValueError, OverflowError, OSError):
                    pass
                side = parse_side(body)
                fresh = published is not None and published.date() == now.date() and published.hour // 2 == now.hour // 2 and published <= now
                accepted = fresh and side is not None and (uid, feed_id) not in used
                history.append('fetch', uid=uid, feed_id=feed_id, create_time=raw_time,
                               body=body, side=side, accepted=accepted,
                               reason='accepted' if accepted else 'stale_unknown_ambiguous_or_duplicate')
                if accepted:
                    predictions.append(dict(uid=uid, side=side, feed_id=feed_id))
            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
                history.append('fetch', uid=uid, feed_id=feed_id, accepted=False,
                               reason='request_or_parse_error', error=str(exc))
    return predictions
