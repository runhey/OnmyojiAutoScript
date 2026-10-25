import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tasks.FrogBoss.frog_oas import OasHistory, parse_side, same_lineup


class OasTests(unittest.TestCase):
    def test_persistence_rewards_and_dedup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history.jsonl'
            store = OasHistory(path)
            decision = store.choose('0' * 512, 20, 10, [
                {'uid': 'a', 'side': 'LEFT'}, {'uid': 'b', 'side': 'RIGHT'}])
            self.assertEqual(store.reliability('a'), .5)
            self.assertEqual(store.choose('0' * 512, 10, 20, [])['id'], decision['id'])
            self.assertIsNone(store.settle('1' * 512, 'LEFT'))
            store.settle('0' * 512, 'LEFT')
            self.assertIsNone(store.settle('0' * 512, 'LEFT'))
            reloaded = OasHistory(path)
            self.assertEqual(reloaded.reliability('a'), 1)
            self.assertEqual(reloaded.reliability('b'), 0)
            self.assertEqual(reloaded.reliability('crowd'), 1)
            second = reloaded.choose('1' * 512, 10, 20, [
                {'uid': 'a', 'side': 'LEFT'}, {'uid': 'b', 'side': 'LEFT'}])
            self.assertEqual(second['scores'], {'LEFT': 0, 'RIGHT': .5})
            self.assertEqual(second['mode'], 'signed_win_rate')
            reloaded.settle('1' * 512, 'RIGHT')
            self.assertEqual(reloaded.reliability('a'), .5)
            self.assertEqual(reloaded.reliability('b'), 0)
            self.assertEqual(reloaded.reliability('crowd'), 1)

    def test_fallback_and_missing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            store = OasHistory(Path(directory) / 'history.jsonl')
            self.assertEqual(store.choose('0' * 512, 1, 2, [])['side'], 'RIGHT')
            self.assertEqual(store.reliability('crowd'), .5)
            with patch('tasks.FrogBoss.frog_oas.random.choice', return_value='LEFT'):
                self.assertEqual(store.choose('1' * 512, 0, 0, [])['side'], 'LEFT')

    def test_cold_start_two_equal_groups(self):
        predictions = [{'uid': str(i), 'side': 'LEFT' if i < 6 else 'RIGHT'} for i in range(9)]
        with tempfile.TemporaryDirectory() as directory:
            store = OasHistory(Path(directory) / 'history.jsonl')
            agreed = store.choose('0' * 512, 20, 10, predictions)
            self.assertEqual(agreed['side'], 'LEFT')
            self.assertEqual(agreed['scores'], {'LEFT': 2, 'RIGHT': 0})
            with patch('tasks.FrogBoss.frog_oas.random.choice', return_value='RIGHT') as choose:
                opposed = store.choose('1' * 512, 10, 20, predictions)
                self.assertEqual(opposed['scores'], {'LEFT': 1, 'RIGHT': 1})
                self.assertEqual(opposed['side'], 'RIGHT')
                choose.assert_called_once_with(('LEFT', 'RIGHT'))

    def test_bet_outcome_settlement_enters_weighted_mode(self):
        for side in ('LEFT', 'RIGHT'):
            for won in (True, False):
                with self.subTest(side=side, won=won), tempfile.TemporaryDirectory() as directory:
                    store = OasHistory(Path(directory) / 'history.jsonl')
                    left, right = (20, 10) if side == 'LEFT' else (10, 20)
                    first = store.choose('0' * 512, left, right, [{'uid': 'a', 'side': side}])
                    result = store.settle('0' * 512, bet_won=won)
                    expected = side if won else ('RIGHT' if side == 'LEFT' else 'LEFT')
                    self.assertEqual(result['winner'], expected)
                    self.assertEqual(result['id'], first['id'])
                    self.assertEqual(result['source'], 'bet_outcome')
                    self.assertEqual(store.reliability('a'), float(won))
                    self.assertIsNone(store.settle('0' * 512, bet_won=won))
                    reloaded = OasHistory(store.path)
                    second = reloaded.choose('1' * 512, left, right, [{'uid': 'a', 'side': side}])
                    self.assertEqual(second['mode'], 'signed_win_rate')

    def test_signed_weights_penalize_wrong_sources_and_leave_newcomers_neutral(self):
        with tempfile.TemporaryDirectory() as directory:
            store = OasHistory(Path(directory) / 'history.jsonl')
            store.append('decision', id='previous', slot='2026-09-28:5', signature='1' * 512, votes={
                'wrong': 'LEFT', 'correct': 'RIGHT', 'crowd': 'LEFT',
            })
            store.append('result', id='previous', winner='RIGHT')
            decision = store.choose('0' * 512, 20, 10, [
                {'uid': 'wrong', 'side': 'LEFT'},
                {'uid': 'correct', 'side': 'RIGHT'},
                {'uid': 'newcomer', 'side': 'LEFT'},
            ])
            self.assertEqual(decision['win_rates'], {
                'wrong': 0, 'correct': 1, 'newcomer': .5, 'crowd': 0,
            })
            self.assertEqual(decision['weights'], {
                'wrong': -.5, 'correct': .5, 'newcomer': 0, 'crowd': -.5,
            })
            self.assertEqual(decision['scores'], {'LEFT': -1, 'RIGHT': .5})
            self.assertEqual(decision['side'], 'RIGHT')
            self.assertEqual(decision['strategy_version'], 3)

    def test_negative_consensus_can_select_the_opposite_side(self):
        with tempfile.TemporaryDirectory() as directory:
            store = OasHistory(Path(directory) / 'history.jsonl')
            store.append('decision', id='previous', slot='2026-09-28:5', signature='1' * 512,
                         votes={'a': 'LEFT'})
            store.append('result', id='previous', winner='RIGHT')
            decision = store.choose('0' * 512, 20, 10, [{'uid': 'a', 'side': 'LEFT'}])
            self.assertEqual(decision['weights'], {'a': -.5, 'crowd': 0})
            self.assertEqual(decision['scores'], {'LEFT': -.5, 'RIGHT': 0})
            self.assertEqual(decision['side'], 'RIGHT')

    def test_signed_weights_use_raw_cumulative_rate_and_randomize_zero_tie(self):
        with tempfile.TemporaryDirectory() as directory:
            store = OasHistory(Path(directory) / 'history.jsonl')
            for index, winner in enumerate(('LEFT', 'RIGHT', 'RIGHT', 'RIGHT')):
                store.append('decision', id=f'seed{index}', slot=f'2026-09-28:{5 + index}',
                             signature='1' * 512, votes={'a': 'LEFT', 'b': 'RIGHT'})
                store.append('result', id=f'seed{index}', winner=winner)
            decision = store.choose('0' * 512, 0, 0, [
                {'uid': 'a', 'side': 'LEFT'}, {'uid': 'b', 'side': 'RIGHT'},
            ])
            self.assertEqual(decision['weights'], {'a': -.25, 'b': .25})
            self.assertEqual(decision['side'], 'RIGHT')
            with patch('tasks.FrogBoss.frog_oas.random.choice', return_value='LEFT') as choose:
                tied = store.choose('1' * 512, 0, 0, [
                    {'uid': 'a', 'side': 'LEFT'}, {'uid': 'b', 'side': 'LEFT'},
                ])
            self.assertEqual(tied['scores'], {'LEFT': 0, 'RIGHT': 0})
            self.assertTrue(tied['random_tiebreak'])
            choose.assert_called_once_with(('LEFT', 'RIGHT'))

    def test_bet_outcome_rejects_missing_or_ambiguous_lineup(self):
        with tempfile.TemporaryDirectory() as directory:
            store = OasHistory(Path(directory) / 'history.jsonl')
            first = store.choose('0' * 512, 20, 10, [])
            self.assertIsNone(store.settle('1' * 512, bet_won=True))
            duplicate = dict(first)
            for key in ('kind', 'version', 'recorded_at'):
                duplicate.pop(key)
            duplicate['id'] = 'another-round'
            store.append('decision', **duplicate)
            self.assertIsNone(store.settle('0' * 512, bet_won=True))
            self.assertFalse(any(e['kind'] == 'result' for e in store.events))

    def test_winner_icons_take_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            store = OasHistory(Path(directory) / 'history.jsonl')
            store.choose('0' * 512, 20, 10, [])
            result = store.settle('0' * 512, 'RIGHT', bet_won=True)
            self.assertEqual(result['winner'], 'RIGHT')
            self.assertEqual(result['source'], 'winner_icons')

    def test_record_page_exact_round_and_dedup(self):
        with tempfile.TemporaryDirectory() as directory:
            store = OasHistory(Path(directory) / 'history.jsonl')
            store.append('decision', id='ten', slot='2026-09-30:5', side='LEFT',
                         votes={'a': 'LEFT', 'crowd': 'LEFT'})
            store.append('decision', id='twelve', slot='2026-09-30:6', side='RIGHT',
                         votes={'a': 'RIGHT', 'crowd': 'LEFT'})
            result = store.settle_record('2026.09.30 12:00', False)
            self.assertEqual(result['id'], 'twelve')
            self.assertEqual(result['winner'], 'LEFT')
            self.assertEqual(result['source'], 'record_page')
            self.assertEqual(store.reliability('a'), 0)
            self.assertEqual(store.reliability('crowd'), 1)
            self.assertIsNone(store.settle_record('2026.09.30 12:00', False))
            self.assertEqual(len([e for e in store.events if e['kind'] == 'result']), 1)
            self.assertEqual(store.settle_record('2026.09.30 10:00', True)['winner'], 'LEFT')

    def test_record_page_rejects_invalid_unknown_and_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            store = OasHistory(Path(directory) / 'history.jsonl')
            store.append('decision', id='a', slot='2026-09-30:6', side='LEFT', votes={})
            for stamp in ('12:00', '2026.09.30 13:00', '2026.09.30 12:30',
                          '2026.02.30 12:00', '2099.09.30 12:00', '2026.09.29 12:00'):
                self.assertIsNone(store.settle_record(stamp, True))
            self.assertIsNone(store.settle_record('2026.09.30 12:00', None))
            self.assertIsNotNone(store.settle_record('2026.09.30 12:00', True))
            self.assertIsNone(store.settle_record('2026.09.30 12:00', False))
            self.assertEqual(store.events[-1]['reason'], 'conflicting_record_result')

    def test_record_page_does_not_guess_between_duplicate_decisions(self):
        with tempfile.TemporaryDirectory() as directory:
            store = OasHistory(Path(directory) / 'history.jsonl')
            for key in ('a', 'b'):
                store.append('decision', id=key, slot='2026-09-30:6', side='LEFT', votes={})
            self.assertIsNone(store.settle_record('2026.09.30 12:00', True))
            self.assertFalse(any(e['kind'] == 'result' for e in store.events))

    def test_selected_side_verifies_bet_and_keeps_raw_result(self):
        with tempfile.TemporaryDirectory() as directory:
            store = OasHistory(Path(directory) / 'history.jsonl')
            store.append('decision', id='a', slot='2026-09-30:6', side='RIGHT',
                         votes={'a': 'RIGHT', 'crowd': 'LEFT'})
            result = store.settle_record('2026.09.30 12:00', False, selected_side='RIGHT')
            self.assertEqual(result['winner'], 'LEFT')
            self.assertEqual(store.reliability('crowd'), 1)
            self.assertEqual(store.reliability('a'), 0)
            self.assertIsNone(store.settle_record('2026.09.30 12:00', False, selected_side='RIGHT'))
            self.assertEqual(len([e for e in store.events if e['kind'] == 'record']), 1)
            self.assertIsNone(store.settle_record('2026.09.30 10:00', True, selected_side='LEFT'))
            self.assertEqual(len([e for e in store.events if e['kind'] == 'record']), 2)

    def test_selected_side_mismatch_does_not_update_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            store = OasHistory(Path(directory) / 'history.jsonl')
            store.append('decision', id='a', slot='2026-09-30:6', side='LEFT', votes={'a': 'LEFT'})
            self.assertIsNone(store.settle_record('2026.09.30 12:00', False, selected_side='RIGHT'))
            self.assertEqual(store.events[-1]['reason'], 'record_bet_side_mismatch')
            self.assertEqual(store.reliability('a'), .5)

    def test_ambiguous_text_and_signature(self):
        self.assertEqual(parse_side('本场押红'), 'LEFT')
        self.assertIsNone(parse_side('不押红，押蓝'))
        self.assertIsNone(parse_side('押红还是押蓝'))
        self.assertTrue(same_lineup('0' * 512, '1' * 10 + '0' * 502))
        self.assertFalse(same_lineup('0' * 512, '1' * 512))


if __name__ == '__main__':
    unittest.main()
