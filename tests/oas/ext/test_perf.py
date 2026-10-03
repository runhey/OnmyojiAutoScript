"""
Tests for oas.ext.perf

Alasio has no tests/ext/test_perf.py, so this module is written from scratch.
Only the deterministic surface is covered: parameter formatting and output
formatting. The benchmark run itself (estimate_iterations, run_performance_test)
is deliberately not exercised, since its assertions would have to be calibrated
against local timings.
"""
import pytest

from oas.ext.perf import PerformanceTest


class TestFormatParameters:
    def test_no_arguments(self):
        assert PerformanceTest()._format_parameters((), {}) == '()'

    def test_positional_only(self):
        assert PerformanceTest()._format_parameters((1, 'a'), {}) == "(1, a)"

    def test_keyword_only(self):
        assert PerformanceTest()._format_parameters((), {'k': 2}) == '(k=2)'

    def test_mixed(self):
        assert PerformanceTest()._format_parameters((1,), {'k': 2}) == '(1, k=2)'

    def test_truncates_beyond_max_length(self):
        args = tuple('x' * 40 for _ in range(10))
        out = PerformanceTest()._format_parameters(args, {}, max_length=120)
        assert out.endswith('...')
        assert len(out) <= 120 + 3

    def test_truncation_keeps_quotes_balanced(self):
        args = ("'" + 'y' * 60,) * 6
        out = PerformanceTest()._format_parameters(args, {}, max_length=120)
        if out.endswith('...'):
            assert out[:-3].count("'") % 2 == 0

    def test_exactly_max_length_is_not_truncated(self):
        # '(' + 'a' * 118 + ')' == 120 chars
        out = PerformanceTest()._format_parameters(('a' * 118,), {}, max_length=120)
        assert not out.endswith('...')
        assert len(out) == 120


class TestFormatOutput:
    @pytest.mark.parametrize('value', [1, 1.5, 'text', True, False])
    def test_scalars_render_as_str(self, value):
        assert PerformanceTest._format_output(value) == str(value)

    def test_short_list_keeps_order(self):
        assert PerformanceTest._format_output([3, 1, 2]) == '[3, 1, 2]'

    def test_long_list_is_summarised(self):
        out = PerformanceTest._format_output(list(range(100)))
        assert out == 'Sequence length: 100'

    def test_short_dict_keeps_order(self):
        assert PerformanceTest._format_output({'b': 1, 'a': 2}) == "{'b': 1, 'a': 2}"

    def test_long_dict_is_summarised(self):
        out = PerformanceTest._format_output({str(i): i for i in range(20)})
        assert out == 'Dict length: 20'

    def test_unknown_object_uses_type_name(self):
        class Widget:
            pass

        assert PerformanceTest._format_output(Widget()) == '<Widget object>'


class TestRegister:
    def test_register_appends_one_entry(self):
        perf = PerformanceTest()
        perf.register(lambda: None)
        assert len(perf.functions) == 1

    def test_register_records_name_and_params(self, capsys):
        perf = PerformanceTest()

        def sample(a, b=1):
            return a + b

        perf.register(sample, 3, b=4)
        entry = perf.functions[0]
        assert entry['name'] == 'sample'
        assert entry['params'] == '(3, b=4)'
        assert entry['args'] == (3,)
        assert entry['kwargs'] == {'b': 4}
        assert 'sample(3, b=4)' in capsys.readouterr().out

    def test_wrapped_callable_forwards_args(self):
        perf = PerformanceTest()
        perf.register(lambda a, b=1: a + b, 3, b=4)
        assert perf.functions[0]['func']() == 7

    def test_context_manager_enter_returns_self(self):
        # Registered nothing, so __exit__ skips run_all_tests() entirely
        perf = PerformanceTest()
        with perf as entered:
            assert entered is perf
        assert perf.functions == []

    def test_exit_does_not_benchmark_when_nothing_registered(self):
        perf = PerformanceTest()
        with perf:
            pass
        assert perf.functions == []