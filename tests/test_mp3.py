"""Tests for MP3 utilities."""

import pathlib
import pytest
from glowtalk.mp3 import concat_mp3_files, _analyze_mp3_frames
import hashlib

def test_mp3_analysis():
    """Test that MP3 analysis works correctly."""
    test_file = pathlib.Path("tests/testdata/test1.mp3")
    assert test_file.exists(), "Test file should exist"

    frame_count, bitrates, mpeg_version, sample_rate, uses_bit_reservoir = _analyze_mp3_frames(test_file)

    assert frame_count > 0, "Should find frames"
    assert len(bitrates) == frame_count, "Should have bitrate for each frame"
    assert mpeg_version == 2, "Test files are MPEG-2"
    assert sample_rate == 24000, "Test files are 24kHz"
    assert not uses_bit_reservoir, "Test files should not use bit reservoir"


def test_concat_mp3_files_success():
    """Test successful concatenation of MP3 files without bit reservoir."""
    test_files = [
        pathlib.Path("tests/testdata/test1.mp3"),
        pathlib.Path("tests/testdata/test2.mp3"),
        pathlib.Path("tests/testdata/test3.mp3")
    ]

    # Verify all test files exist
    for f in test_files:
        assert f.exists(), f"Test file {f} should exist"

    # Get expected frame counts
    expected_frames = []
    expected_bytes = 0
    for f in test_files:
        frame_count, _, _, _, uses_reservoir = _analyze_mp3_frames(f)
        assert not uses_reservoir, f"Test file {f} should not use bit reservoir"
        expected_frames.append(frame_count)
        expected_bytes += f.stat().st_size

    # Test concatenation
    frame_count = 0
    total_bytes = 0
    for frame_data in concat_mp3_files(test_files):
        frame_count += 1
        total_bytes += len(frame_data)

    assert frame_count == sum(expected_frames), "Should get all frames from all files"
    # Note: total_bytes will be less than file sizes due to ID3 tags being stripped
    assert total_bytes > 0, "Should have some data"
    # Calculate the sha256 of the concatenated data for verification
    sha256 = hashlib.sha256()
    for frame_data in concat_mp3_files(test_files):
        sha256.update(frame_data)
    digest = sha256.hexdigest()
    # Known good value, calculated previously.
    expected_digest = "52d76bafd5405248cffcdf4e5517544218bee0730131704cce6cba3437ea7758"
    assert digest == expected_digest, "Concatenated data hash should match expected"


def test_concat_mp3_files_with_bit_reservoir_fails():
    """Test that concatenation fails when files use bit reservoir."""
    # Use our test file that uses bit reservoir
    bit_reservoir_file = pathlib.Path("tests/testdata/test_with_bit_reservoir.mp3")
    assert bit_reservoir_file.exists(), "Test file with bit reservoir should exist"

    # Verify it uses bit reservoir
    _, _, _, _, uses_reservoir = _analyze_mp3_frames(bit_reservoir_file)
    assert uses_reservoir, "Test file should use bit reservoir"

    with pytest.raises(ValueError, match="uses bit reservoir"):
        list(concat_mp3_files([bit_reservoir_file]))


def test_concat_mixed_files_fails():
    """Test that concatenation fails when mixing files with and without bit reservoir."""
    test_file_good = pathlib.Path("tests/testdata/test1.mp3")
    test_file_bad = pathlib.Path("tests/testdata/test_with_bit_reservoir.mp3")

    assert test_file_good.exists(), "Good test file should exist"
    assert test_file_bad.exists(), "Bad test file should exist"

    # Verify the good file doesn't use bit reservoir
    _, _, _, _, uses_reservoir_good = _analyze_mp3_frames(test_file_good)
    assert not uses_reservoir_good, "Good test file should not use bit reservoir"

    # Verify the bad file uses bit reservoir
    _, _, _, _, uses_reservoir_bad = _analyze_mp3_frames(test_file_bad)
    assert uses_reservoir_bad, "Bad test file should use bit reservoir"

    with pytest.raises(ValueError, match="uses bit reservoir"):
        list(concat_mp3_files([test_file_good, test_file_bad]))


def test_frame_extraction_yields_valid_frames():
    """Test that frame extraction yields valid frame data."""
    from glowtalk.mp3 import _extract_mp3_frames

    test_file = pathlib.Path("tests/testdata/test1.mp3")
    assert test_file.exists(), "Test file should exist"

    frames = list(_extract_mp3_frames(test_file))
    assert len(frames) > 0, "Should extract some frames"

    # Check that each frame starts with valid MP3 sync
    for i, frame in enumerate(frames):
        assert len(frame) > 4, f"Frame {i} should have data"
        assert frame[0] == 0xFF, f"Frame {i} should start with sync byte"
        assert (frame[1] & 0xE0) == 0xE0, f"Frame {i} should have valid sync pattern"


if __name__ == "__main__":
    # Run tests directly if executed as script
    test_mp3_analysis()
    test_concat_mp3_files_success()
    test_frame_extraction_yields_valid_frames()
    print("All tests passed!")
