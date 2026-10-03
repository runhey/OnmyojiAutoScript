from script.misc.timer import timer


class TestTimerDecorator:
    """Test timer decorator"""

    def test_timer_decorator_basic(self, capsys):
        """Test basic decorator functionality - uses real time but verifies output"""

        @timer
        def sample_function():
            return "result"

        result = sample_function()
        assert result == "result"

        # Verify print output
        captured = capsys.readouterr()
        assert 'sample_function:' in captured.out
        assert 's' in captured.out

    def test_timer_decorator_with_args(self, capsys):
        """Test decorator handles functions with arguments"""

        @timer
        def add_numbers(a, b, multiplier=1):
            return (a + b) * multiplier

        result = add_numbers(3, 5, multiplier=2)
        assert result == 16

        captured = capsys.readouterr()
        assert 'add_numbers:' in captured.out
