from oas.logger import logger


def test_logger_set_level():
    """
    Test logger.set_level() and method replacement behavior.
    """
    with logger.mock_capture_writer() as capture:
        # Reset to INFO
        logger.set_level('INFO')

        # 1. INFO level should show info and hide debug
        logger.info("Info message")
        logger.debug("Debug message")
        assert capture.fd.any_contains("Info message")
        assert not capture.fd.any_contains("Debug message")
        capture.clear()

        # 2. DEBUG level should show both
        logger.set_level('DEBUG')
        logger.info("Info message 2")
        logger.debug("Debug message 2")
        assert capture.fd.any_contains("Info message 2")
        assert capture.fd.any_contains("Debug message 2")
        capture.clear()

        # 3. WARNING level should hide info and debug
        logger.set_level('WARNING')
        logger.info("Info message 3")
        logger.warning("Warning message 3")
        assert not capture.fd.any_contains("Info message 3")
        assert capture.fd.any_contains("Warning message 3")
        capture.clear()


def test_level_propagation():
    """
    Test that log level is propagated through bind() and unbind().
    """
    with logger.mock_capture_writer() as capture:
        # Set to ERROR level
        logger.set_level('ERROR')

        # 1. bind() should inherit ERROR level
        bound = logger.bind(user="alice")
        bound.info("Info message")
        bound.error("Error message")
        assert not capture.fd.any_contains("Info message")
        assert capture.fd.any_contains("Error message")
        capture.clear()

        # 2. bound logger sets its own level (although set_level updates the instance)
        # Actually set_level modifies the instance, let's test if it affects bound
        bound.set_level('DEBUG')
        bound.debug("Bound debug message")
        logger.debug("Logger debug message")
        assert capture.fd.any_contains("Bound debug message")
        assert not capture.fd.any_contains("Logger debug message")
        capture.clear()

        # 3. bind from bound should inherit DEBUG
        deeper = bound.bind(action="test")
        deeper.debug("Deeper debug message")
        assert capture.fd.any_contains("Deeper debug message")
        capture.clear()

        # 4. unbind should also inherit level
        unbound = deeper.unbind("user")
        unbound.debug("Unbound debug message")
        assert capture.fd.any_contains("Unbound debug message")
        capture.clear()


def test_custom_methods_level():
    """
    Test that custom methods like hr, attr, raw are affected by log level.
    Most custom methods are mapped to INFO level (20).
    """
    with logger.mock_capture_writer() as capture:
        # 1. Set to WARNING, INFO-based methods should be hidden
        logger.set_level('WARNING')
        logger.raw("Raw message")
        logger.hr("HR message")
        logger.attr("key", "value")
        logger.attr_align("key", "value")

        assert not capture.fd.any_contains("Raw message")
        assert not capture.fd.any_contains("HR message")
        assert not capture.fd.any_contains("key")
        capture.clear()

        # 2. Set to INFO, they should appear
        logger.set_level('INFO')
        logger.raw("Raw message 2")
        logger.hr("HR message 2")
        logger.attr("key2", "value2")

        assert capture.fd.any_contains("Raw message 2")
        assert capture.fd.any_contains("HR message 2".upper())
        assert capture.fd.any_contains("[key2] value2")
        capture.clear()


def test_invalid_level():
    """
    Test that invalid level string defaults to INFO.
    """
    with logger.mock_capture_writer() as capture:
        # Set to something invalid
        logger.set_level('INVALID_LEVEL')

        # Should default to INFO
        logger.info("Info level")
        logger.debug("Debug level")
        assert capture.fd.any_contains("Info level")
        assert not capture.fd.any_contains("Debug level")
        capture.clear()


def test_level_switch_multiple_times():
    """
    Test setting log level multiple times, especially increasing and then decreasing.
    This ensures that original methods are correctly restored from the class.
    """
    with logger.mock_capture_writer() as capture:
        # 1. Start with INFO
        logger.set_level('INFO')
        logger.info("Info 1")
        logger.debug("Debug 1")
        assert capture.fd.any_contains("Info 1")
        assert not capture.fd.any_contains("Debug 1")
        capture.clear()

        # 2. Switch to WARNING (Increase level)
        logger.set_level('WARNING')
        logger.info("Info 2")
        logger.warning("Warning 2")
        assert not capture.fd.any_contains("Info 2")
        assert capture.fd.any_contains("Warning 2")
        capture.clear()

        # 3. Switch to DEBUG (Decrease level)
        logger.set_level('DEBUG')
        logger.info("Info 3")
        logger.debug("Debug 3")
        assert capture.fd.any_contains("Info 3")
        assert capture.fd.any_contains("Debug 3")
        capture.clear()

        # 4. Switch back to INFO
        logger.set_level('INFO')
        logger.info("Info 4")
        logger.debug("Debug 4")
        assert capture.fd.any_contains("Info 4")
        assert not capture.fd.any_contains("Debug 4")
        capture.clear()

        # 5. Switch to CRITICAL
        logger.set_level('CRITICAL')
        logger.error("Error 5")
        logger.critical("Critical 5")
        assert not capture.fd.any_contains("Error 5")
        assert capture.fd.any_contains("Critical 5")
        capture.clear()

        # 6. Switch back to INFO from CRITICAL
        logger.set_level('INFO')
        logger.error("Error 6")
        logger.info("Info 6")
        assert capture.fd.any_contains("Error 6")
        assert capture.fd.any_contains("Info 6")
        capture.clear()


def test_hr_minimum_fill():
    """
    Test that hr1, hr2, hr3 always have at least 5 fill characters
    on each side of the title, regardless of title length.
    """
    with logger.mock_capture_writer() as capture:
        logger.set_level('INFO')

        # 1. Empty title - should still show 5+ fill chars each side
        logger.hr1('')
        assert ''.join(capture.fd.logs[:1]) == ("""\
=================================================  =================================================
""")
        assert capture.fd.logs[1].endswith('| INFO | \n')
        capture.clear()

        logger.hr2('')
        assert ''.join(capture.fd.logs[:1]) == ("""\
-------------------------------------------------  -------------------------------------------------
""")
        assert capture.fd.logs[1].endswith('| INFO | \n')
        capture.clear()

        logger.hr3('')
        assert capture.fd.logs[0].endswith("""\
...................  ...................
""")
        capture.clear()

        # 2. Very short title
        logger.hr1('A')
        assert ''.join(capture.fd.logs[:1]) == ("""\
================================================ A =================================================
""")
        assert capture.fd.logs[1].endswith('| INFO | A\n')
        capture.clear()

        logger.hr2('A')
        assert ''.join(capture.fd.logs[:1]) == ("""\
------------------------------------------------ A -------------------------------------------------
""")
        assert capture.fd.logs[1].endswith('| INFO | A\n')
        capture.clear()

        logger.hr3('A')
        assert capture.fd.logs[0].endswith("""\
.................. A ...................
""")
        capture.clear()

        # 3. Long title that exceeds default width, requiring extension
        logger.hr1('X' * 100)
        assert ''.join(capture.fd.logs[:1]) == ("""\
===== XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX =====
""")
        assert capture.fd.logs[1].endswith('| INFO | ' + 'X' * 100 + '\n')
        capture.clear()

        logger.hr2('Y' * 100)
        assert ''.join(capture.fd.logs[:1]) == ("""\
----- YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY -----
""")
        assert capture.fd.logs[1].endswith('| INFO | ' + 'Y' * 100 + '\n')
        capture.clear()

        # 4. Title that exceeds hr3 default width (40) -> need >28 chars
        logger.hr3('Z' * 40)
        assert capture.fd.logs[0].endswith("""\
..... ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ .....
""")
        capture.clear()


def test_hr0_auto_extend():
    """
    Test that hr0 auto-extends the box when title is too long.
    Short title should keep default 98-char interior.
    """
    with logger.mock_capture_writer() as capture:
        logger.set_level('INFO')

        # 1. Short title - maintain 98-char interior
        logger.hr0('SHORT')
        assert ''.join(capture.fd.logs[:3]) == ("""\
+==================================================================================================+
|                                              SHORT                                               |
+==================================================================================================+
""")
        assert capture.fd.logs[3].endswith('| INFO | SHORT\n')
        capture.clear()

        # 2. Long title (95 chars) - should extend interior
        logger.hr0('X' * 95)
        assert ''.join(capture.fd.logs[:3]) == ("""\
+=========================================================================================================+
|     XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX     |
+=========================================================================================================+
""")
        assert capture.fd.logs[3].endswith('| INFO | ' + 'X' * 95 + '\n')
        capture.clear()

        # 3. Very long title (200 chars) - should extend significantly
        logger.hr0('Y' * 200)
        assert ''.join(capture.fd.logs[:3]) == ("""\
+==================================================================================================================================================================================================================+
|     YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY     |
+==================================================================================================================================================================================================================+
""")
        assert capture.fd.logs[3].endswith('| INFO | ' + 'Y' * 200 + '\n')
        capture.clear()
