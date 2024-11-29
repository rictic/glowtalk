from unittest.mock import Mock, patch
import io
import pytest
from glowtalk.server import ProgressReporter

@pytest.fixture
def mock_time():
    with patch('time.time') as mock:
        # Return increasing timestamps (0, 10, 20, etc.) for each call
        mock.side_effect = [i * 10 for i in range(10)]
        yield mock


@pytest.fixture
def string_output():
    return io.StringIO()


def test_first_report_prints_nothing(string_output):
    reporter = ProgressReporter(outstream=string_output)
    reporter.report(100)
    assert string_output.getvalue() == ""


def test_second_report_prints_nothing(string_output):
    reporter = ProgressReporter(outstream=string_output)
    reporter.report(100)
    reporter.report(90)
    assert string_output.getvalue() == ""


def test_third_report_shows_estimate(string_output, mock_time):
    reporter = ProgressReporter(outstream=string_output)

    # Report progress at different timestamps
    reporter.report(100)  # t=0
    reporter.report(90)   # t=10
    reporter.report(80)   # t=20

    # Calculate expected rate: 10 items per 10 seconds = 1 item/second
    # With 80 items remaining, should estimate 80 seconds

    output = string_output.getvalue()
    assert "80 posts remaining" in output
    assert "0:01:20" in output  # 80 seconds formatted as timedelta


def test_handles_zero_remaining(string_output, mock_time):
    reporter = ProgressReporter(outstream=string_output)

    reporter.report(20)
    reporter.report(10)
    reporter.report(0)

    output = string_output.getvalue()
    assert "0 posts remaining" in output


def test_handles_no_progress(string_output, mock_time):
    reporter = ProgressReporter(outstream=string_output)

    reporter.report(100)
    reporter.report(100)
    reporter.report(100)

    output = string_output.getvalue()
    assert "100 posts remaining" in output
    # Should still make an estimate even with no progress


def test_accurate_time_estimate(string_output, mock_time):
    reporter = ProgressReporter(outstream=string_output)

    # Simulate processing 1 post every 3 seconds
    mock_time.side_effect = [i * 3 for i in range(10)]
    reporter.report(100)  # t=0
    reporter.report(99)   # t=3
    reporter.report(98)   # t=6

    output = string_output.getvalue()
    assert "98 posts remaining" in output
    # With 98 posts remaining at 1 post/3sec, should be ~294 seconds
    assert "0:04:54" in output  # 294 seconds formatted as timedelta

def test_maintains_accurate_estimate_over_time(string_output, mock_time):
    reporter = ProgressReporter(outstream=string_output)

    # Simulate slower progress - 1 post every 3 seconds
    mock_time.side_effect = [i * 3 for i in range(10)]

    reporter.report(724)  # t=0
    reporter.report(723)  # t=3
    reporter.report(722)  # t=6

    output = string_output.getvalue()
    assert "722 posts remaining" in output
    # At 1 post/3sec with 722 remaining, should be ~2166 seconds = ~36 minutes
    assert "0:36:" in output

def test_estimate_updates_with_changing_rates(string_output, mock_time):
    reporter = ProgressReporter(outstream=string_output, history_size=3)

    # Start fast (1 post/second)
    mock_time.side_effect = [0, 1, 2]
    reporter.report(100)
    reporter.report(99)
    reporter.report(98)

    first_output = string_output.getvalue()
    assert "0:01:38" in first_output  # ~98 seconds

    # Then slow down (1 post/3 seconds)
    mock_time.side_effect = [3, 6, 9]
    reporter.report(97)
    reporter.report(96)
    reporter.report(95)

    second_output = string_output.getvalue()
    assert "0:04:45" in second_output  # ~285 seconds

