from script.misc.timer import Timer
from oas.testing.patch_time import PatchTime


class TestTimerInitialization:
    """Test Timer initialization"""

    def test_init_basic(self):
        """Test basic initialization"""
        t = Timer(limit=5.0, count=10)
        assert t.limit == 5.0
        assert t.count == 10
        assert t._start == 0.0
        assert t._access == 0

    def test_init_default_count(self):
        """Test default count value"""
        t = Timer(limit=3.0)
        assert t.limit == 3.0
        assert t.count == 0

    def test_from_seconds(self):
        """Test from_seconds class method"""
        t = Timer.from_seconds(limit=10, speed=0.5)
        assert t.limit == 10
        assert t.count == 20  # 10 / 0.5 = 20

    def test_from_seconds_slow_device(self):
        """Test slow device scenario"""
        t = Timer.from_seconds(limit=5, speed=1.0)
        assert t.limit == 5
        assert t.count == 5  # 5 / 1.0 = 5

    def test_init_negative_limit(self):
        """Test __init__ with negative limit clamps to 0"""
        t = Timer(limit=-5.0, count=10)
        assert t.limit == 0.0
        assert t.count == 10

    def test_init_negative_count(self):
        """Test __init__ with negative count clamps to 0"""
        t = Timer(limit=5.0, count=-3)
        assert t.limit == 5.0
        assert t.count == 0

    def test_init_both_negative(self):
        """Test __init__ with both negative"""
        t = Timer(limit=-5.0, count=-3)
        assert t.limit == 0.0
        assert t.count == 0


class TestFromSeconds:
    """Test from_seconds class method with T_TIMER_LIMIT types"""

    def test_float_limit(self):
        """from_seconds with float limit"""
        t = Timer.from_seconds(limit=7.5, speed=0.5)
        assert t.limit == 7.5
        assert t.count == 15  # 7.5 / 0.5 = 15

    def test_tuple_int_int(self):
        """from_seconds with (int, int) tuple"""
        t = Timer.from_seconds(limit=(10, 3))
        assert t.limit == 10
        assert t.count == 3

    def test_tuple_float_int(self):
        """from_seconds with (float, int) tuple"""
        t = Timer.from_seconds(limit=(7.5, 3))
        assert t.limit == 7.5
        assert t.count == 3

    def test_timer_object(self):
        """from_seconds with Timer object returns the same Timer"""
        original = Timer(limit=10, count=5)
        result = Timer.from_seconds(limit=original)
        assert result is original
        assert result.limit == 10
        assert result.count == 5

    def test_tuple_negative_limit(self):
        """from_seconds with negative limit in tuple clamps to 0"""
        t = Timer.from_seconds(limit=(-10, 3))
        assert t.limit == 0
        assert t.count == 3

    def test_tuple_negative_count(self):
        """from_seconds with negative count in tuple clamps to 0"""
        t = Timer.from_seconds(limit=(10, -5))
        assert t.limit == 10
        assert t.count == 0

    def test_default_speed(self):
        """from_seconds with default speed (0.5)"""
        t = Timer.from_seconds(limit=10)
        assert t.limit == 10
        assert t.count == 20  # 10 / 0.5 = 20


class TestTimerStart:
    """Test Timer start functionality"""

    def test_start(self):
        """Test starting the timer"""
        with PatchTime(100.0):
            t = Timer(limit=5.0, count=10)

            assert not t.started()
            t.start()
            assert t.started()
            assert t._start == 100.0
            assert t._access == 0

    def test_start_multiple_times(self):
        """Test multiple starts don't reset the timer"""
        with PatchTime(100.0) as pt:
            t = Timer(limit=5.0, count=10)

            t.start()
            first_start = t._start
            pt.shift(5.0)  # advance time to 105.0
            t.start()  # Second start should not change _start
            assert t._start == first_start

    def test_started_before_start(self):
        """Test started() returns False before starting"""
        t = Timer(limit=5.0)
        assert not t.started()


class TestTimerCurrent:
    """Test current time and count methods"""

    def test_current_time_not_started(self):
        """Test current time when not started"""
        t = Timer(limit=5.0)
        assert t.current_time() == 0.0

    def test_current_time_after_start(self):
        """Test current time after starting"""
        with PatchTime(100.0) as pt:
            t = Timer(limit=5.0)

            t.start()
            pt.shift(3.5)  # advance to 103.5
            elapsed = t.current_time()
            assert elapsed == 3.5

    def test_current_time_negative_protection(self):
        """Test protection against time going backwards"""
        with PatchTime(100.0) as pt:
            t = Timer(limit=5.0)

            t.start()
            pt.shift(-5.0)  # go backwards to 95.0
            elapsed = t.current_time()
            assert elapsed == 0.0  # Should return 0 instead of negative

    def test_current_count(self):
        """Test current access count"""
        t = Timer(limit=5.0, count=10)
        assert t.current_count() == 0

        t.add_count()
        assert t.current_count() == 1

        t.add_count()
        assert t.current_count() == 2


class TestTimerReached:
    """Test reached() method"""

    def test_reached_not_started(self):
        """Test reached() returns True when not started (fast first try)"""
        t = Timer(limit=5.0, count=10)
        assert t.reached()

    def test_reached_time_not_enough(self):
        """Test returns False when time is insufficient"""
        with PatchTime(100.0) as pt:
            t = Timer(limit=5.0, count=10)

            t.start()
            pt.shift(2.0)  # Only 2 seconds elapsed
            # Simulate 10 accesses (exceeds count but time not enough)
            t._access = 10

            assert not t.reached()  # Time not enough

    def test_reached_count_not_enough(self):
        """Test returns False when access count is insufficient"""
        with PatchTime(100.0) as pt:
            t = Timer(limit=5.0, count=10)

            t.start()
            pt.shift(6.0)  # 6 seconds elapsed
            # Only 5 accesses
            t._access = 5

            assert not t.reached()  # Count not enough

    def test_reached_both_conditions_met(self):
        """Test returns True when both time and count conditions are met"""
        with PatchTime(100.0) as pt:
            t = Timer(limit=5.0, count=10)

            t.start()
            pt.shift(6.0)  # 6 seconds elapsed
            # 10 accesses
            t._access = 10

            assert t.reached()  # Both time and count are sufficient

    def test_reached_increments_access(self):
        """Test each reached() call increments access count"""
        with PatchTime(100.0):
            t = Timer(limit=5.0, count=10)

            t.start()
            initial_access = t._access
            t.reached()
            assert t._access == initial_access + 1


class TestTimerReset:
    """Test reset functionality"""

    def test_reset(self):
        """Test reset() resets the timer"""
        with PatchTime(100.0) as pt:
            t = Timer(limit=5.0, count=10)

            t.start()
            t._access = 5

            pt.shift(50.0)  # advance to 150.0
            t.reset()
            assert t._start == 150.0
            assert t._access == 0

    def test_clear(self):
        """Test clear() clears the timer"""
        t = Timer(limit=5.0, count=10)
        t._start = 100.0
        t._access = 5

        t.clear()
        assert t._start == 0.0
        assert t._access == 10  # Set to count value

    def test_reached_and_reset_true(self):
        """Test reached_and_reset() when condition is met"""
        with PatchTime(100.0) as pt:
            t = Timer(limit=5.0, count=10)

            t.start()
            t._access = 10
            pt.shift(6.0)  # advance to 106.0

            result = t.reached_and_reset()
            assert result is True
            assert t._access == 0  # Should be reset

    def test_reached_and_reset_false(self):
        """Test reached_and_reset() when condition is not met"""
        with PatchTime(100.0) as pt:
            t = Timer(limit=5.0, count=10)

            t.start()
            t._access = 5
            pt.shift(2.0)  # advance to 102.0

            result = t.reached_and_reset()
            assert result is False
            # reached() increments _access first, so _access becomes 6
            assert t._access == 6


class TestTimerWait:
    """Test wait() method"""

    def test_wait_with_remaining_time(self):
        """Test waiting when there is remaining time"""
        with PatchTime(100.0) as pt:
            t = Timer(limit=5.0, count=10)

            t.start()
            pt.shift(2.0)  # advance to 102.0

            # Capture current sleep calls before wait
            pt.clear_sleep_calls()
            t.wait()

            # Should wait for 5 - 2 = 3 seconds
            assert len(pt.sleep_calls) == 1
            assert abs(pt.sleep_calls[0] - 3.0) < 0.001

            # Time should have advanced by the sleep duration
            assert t.current_time() == 5.0

    def test_wait_with_no_remaining_time(self):
        """Test no waiting when time has already expired"""
        with PatchTime(100.0) as pt:
            t = Timer(limit=5.0, count=10)

            t.start()
            pt.shift(6.0)  # advance to 106.0, already timed out

            pt.clear_sleep_calls()
            t.wait()

            # Should not call sleep
            assert len(pt.sleep_calls) == 0


class TestTimerIntegration:
    """Integration tests"""

    def test_typical_usage_loop(self):
        """Test typical loop usage scenario"""
        with PatchTime(100.0) as pt:
            t = Timer(limit=5.0, count=3)
            execution_count = 0

            # Simulate loop
            for i in range(3):
                if t.reached():
                    execution_count += 1
                    t.reset()
                pt.shift(1.0)  # advance by 1 second each iteration

            # First time: not started, returns True, executes
            # Subsequent times depend on conditions
            assert execution_count >= 1

    def test_chaining_methods(self):
        """Test method chaining"""
        with PatchTime(100.0):
            t = Timer(limit=5.0, count=10)

            result = t.start().add_count().add_count()
            assert result is t  # Ensure returns self
            assert t._access == 2

    def test_str_representation(self):
        """Test string representation"""
        t = Timer(limit=5.0, count=10)
        t._access = 3

        string_repr = str(t)
        assert "Timer" in string_repr
        assert "5" in string_repr  # limit
        assert "3" in string_repr  # access count
        assert "10" in string_repr  # count
