import pytest
import trio
import trio.testing

from oas.backend.reactive.background import BackgroundTask


class MockBackgroundTask(BackgroundTask):
    def __init__(self):
        super().__init__()
        self.run_count = 0

    async def task_run(self):
        """
        Mock implementation of task_run to track execution count.
        """
        self.run_count += 1


@pytest.mark.trio
async def test_background_task_basic(autojump_clock):
    """
    Test standard execution and periodic loop.
    1. Default not running.
    2. Runs once after trigger.
    3. Runs periodically every 2 seconds.
    """
    task = MockBackgroundTask()
    async with trio.open_nursery() as nursery:
        # 1. Default not running: Only starts after calling trigger()
        assert task.run_count == 0

        # 2. Execute and cycle: After executing once, re-executes every 2 seconds by default
        task.task_trigger(nursery)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 1

        # Wait for next periodic run (interval is 2s)
        await trio.sleep(task.recurrence)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 2

        await trio.sleep(task.recurrence)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 3

        task.task_shutdown()


@pytest.mark.trio
async def test_background_task_trigger_reset(autojump_clock):
    """
    Test reset logic: If trigger() is called during wait, it should interrupt wait and run immediately.
    """
    task = MockBackgroundTask()
    async with trio.open_nursery() as nursery:
        task.task_trigger(nursery)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 1

        # Wait for 1 second (halfway through the 2s interval)
        await trio.sleep(1)
        assert task.run_count == 1

        # Trigger again during wait period
        task.task_trigger(nursery)
        await trio.testing.wait_all_tasks_blocked()
        # Should run immediately and reset timer
        assert task.run_count == 2

        # Should NOT run at the original 2s mark (which would be 1s from now)
        await trio.sleep(1.5)
        assert task.run_count == 2

        # Should run 2s after the second trigger
        await trio.sleep(0.6)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 3

        task.task_shutdown()


@pytest.mark.trio
async def test_background_task_stop(autojump_clock):
    """
    Test stop function: Interrupts current execution and wait, goes to idle state.
    """
    task = MockBackgroundTask()
    async with trio.open_nursery() as nursery:
        task.task_trigger(nursery)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 1

        # Stop current execution and wait period
        task.task_stop()
        # Should be in idle state, not running periodically
        await trio.sleep(5)
        assert task.run_count == 1

        # Should be wakeable by trigger()
        task.task_trigger(nursery)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 2

        task.task_shutdown()


@pytest.mark.trio
async def test_background_task_shutdown(autojump_clock):
    """
    Test shutdown logic:
    - fully=False: Destroy background task, trigger() can recreate it.
    - fully=True: Permanently disable.
    """
    task = MockBackgroundTask()
    async with trio.open_nursery() as nursery:
        # Test fully=False
        task.task_trigger(nursery)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 1
        assert task._shutdown_scope is not None

        task.task_shutdown(fully=False)
        await trio.testing.wait_all_tasks_blocked()
        assert task._shutdown_scope is None

        # Re-triggerable
        task.task_trigger(nursery)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 2
        assert task._shutdown_scope is not None

        # Test fully=True
        task.task_shutdown(fully=True)
        await trio.testing.wait_all_tasks_blocked()
        assert task._permanently_disabled is True
        assert task._shutdown_scope is None

        # Cannot be restarted
        task.task_trigger(nursery)
        assert task._shutdown_scope is None
        assert task.run_count == 2


@pytest.mark.trio
async def test_background_task_merge_startup(autojump_clock):
    """
    Test 1: Multiple triggers during startup/first task are merged.
    """
    task = MockBackgroundTask()
    task.drop_threshold = 0
    async with trio.open_nursery() as nursery:
        # Trigger multiple times before task starts
        task.task_trigger(nursery)
        task.task_trigger(nursery)
        task.task_trigger(nursery)

        await trio.testing.wait_all_tasks_blocked()
        # Should have run once despite multiple triggers
        assert task.run_count == 1

        # Wait a bit to ensure no extra runs happen
        await trio.sleep(0.5)
        assert task.run_count == 1

        task.task_shutdown()


@pytest.mark.trio
async def test_background_task_merge_during_execution(autojump_clock):
    """
    Test 2: Multiple triggers during task execution are merged (discarded).
    """

    class RecursiveTriggerTask(MockBackgroundTask):
        def __init__(self, nursery):
            super().__init__()
            self.nursery = nursery

        async def task_run(self):
            await super().task_run()
            if self.run_count == 1:
                # Trigger multiple times during execution
                # Since task_run is sync and called from within _task_loop
                self.task_trigger(self.nursery)
                self.task_trigger(self.nursery)

    async with trio.open_nursery() as nursery:
        task = RecursiveTriggerTask(nursery)
        task.drop_threshold = 0

        task.task_trigger(nursery)
        await trio.testing.wait_all_tasks_blocked()

        # First run should have triggered it twice more, but they should be dropped
        assert task.run_count == 1

        # Wait to confirm no delayed runs
        await trio.sleep(0.5)
        assert task.run_count == 1

        task.task_shutdown()


@pytest.mark.trio
async def test_background_task_drop_threshold(autojump_clock):
    """
    Test 3: Triggers within drop_threshold are discarded.
    """
    task = MockBackgroundTask()
    task.drop_threshold = 1.0
    async with trio.open_nursery() as nursery:
        task.task_trigger(nursery)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 1

        # Trigger immediately (well within 1s threshold)
        task.task_trigger(nursery)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 1

        # Wait for threshold to pass
        await trio.sleep(1.1)
        task.task_trigger(nursery)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 2

        task.task_shutdown()


@pytest.mark.trio
async def test_background_task_none_recurrence(autojump_clock):
    """
    Test when recurrence is None:
    - Runs once after trigger.
    - Does NOT run again automatically.
    - Can be triggered manually again.
    """
    task = MockBackgroundTask()
    task.recurrence = None
    async with trio.open_nursery() as nursery:
        # Trigger manually
        task.task_trigger(nursery)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 1

        # Wait for a long time, should NOT run automatically
        await trio.sleep(10)
        assert task.run_count == 1

        # Trigger manually again
        task.task_trigger(nursery)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 2

        task.task_shutdown()


@pytest.mark.trio
async def test_background_task_multiple_stop(autojump_clock):
    """
    Test multiple stops followed by a trigger:
    Calling task_stop() multiple times should not break internal state
    and it should be wakeable by trigger() afterwards.
    """
    task = MockBackgroundTask()
    async with trio.open_nursery() as nursery:
        task.task_trigger(nursery)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 1

        # Stop multiple times
        task.task_stop()
        task.task_stop()
        task.task_stop()

        # Should be wakeable by trigger()
        await trio.sleep(10)
        task.task_trigger(nursery)
        await trio.testing.wait_all_tasks_blocked()
        assert task.run_count == 2

        task.task_shutdown()
