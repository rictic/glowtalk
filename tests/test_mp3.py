"""Tests for MP3 utilities."""

import hashlib
import pathlib
import pytest
from glowtalk.mp3 import concat_mp3_files, Mp3Parser

def test_mp3_analysis():
    """Test that MP3 analysis works correctly."""
    test_file = pathlib.Path("tests/testdata/test1.mp3")
    assert test_file.exists(), "Test file should exist"

    with open(test_file, 'rb') as f:
        parser = Mp3Parser(f)
        frames = list(parser)

    assert len(frames) > 0, "Should find frames"
    first_frame = frames[0]
    assert first_frame.mpeg_version == 2, "Test files are MPEG-2"
    assert first_frame.sample_rate == 24000, "Test files are 24kHz"
    assert not any(frame.uses_bit_reservoir for frame in frames), "Test files should not use bit reservoir"


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
        with open(f, 'rb') as file:
            parser = Mp3Parser(file)
            frames = list(parser)
            assert not any(frame.uses_bit_reservoir for frame in frames), f"Test file {f} should not use bit reservoir"
            expected_frames.append(len(frames))
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
    expected_digest = "0c6c1b667d9be33ba07bb41286af235ad1c64ed59dac8bdf4a2c7afeeb3f446b"
    assert digest == expected_digest, "Concatenated data hash should match expected"


def test_concat_mp3_files_with_bit_reservoir_fails():
    """Test that concatenation fails when files use bit reservoir."""
    # Use our test file that uses bit reservoir
    bit_reservoir_file = pathlib.Path("tests/testdata/test_with_bit_reservoir.mp3")
    assert bit_reservoir_file.exists(), "Test file with bit reservoir should exist"

    # Verify it uses bit reservoir
    with open(bit_reservoir_file, 'rb') as f:
        parser = Mp3Parser(f)
        frames = list(parser)
        uses_reservoir = any(frame.uses_bit_reservoir for frame in frames)
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
    with open(test_file_good, 'rb') as f:
        parser = Mp3Parser(f)
        frames = list(parser)
        uses_reservoir_good = any(frame.uses_bit_reservoir for frame in frames)
    assert not uses_reservoir_good, "Good test file should not use bit reservoir"

    # Verify the bad file uses bit reservoir
    with open(test_file_bad, 'rb') as f:
        parser = Mp3Parser(f)
        frames = list(parser)
        uses_reservoir_bad = any(frame.uses_bit_reservoir for frame in frames)
    assert uses_reservoir_bad, "Bad test file should use bit reservoir"

    with pytest.raises(ValueError, match="uses bit reservoir"):
        list(concat_mp3_files([test_file_good, test_file_bad]))


def test_frame_extraction_yields_valid_frames():
    """Test that frame extraction yields valid frame data."""
    test_file = pathlib.Path("tests/testdata/test1.mp3")
    assert test_file.exists(), "Test file should exist"

    with open(test_file, 'rb') as f:
        parser = Mp3Parser(f)
        frames = list(parser)

    assert len(frames) > 0, "Should extract some frames"

    # Check that each frame starts with valid MP3 sync
    for i, frame in enumerate(frames):
        assert len(frame.data) > 4, f"Frame {i} should have data"
        assert frame.data[0] == 0xFF, f"Frame {i} should start with sync byte"
        assert (frame.data[1] & 0xE0) == 0xE0, f"Frame {i} should have valid sync pattern"


def test_vbr_header_stripping():
    """Test that VBR headers are stripped during concatenation."""
    test_file = pathlib.Path("tests/testdata/test1.mp3")
    assert test_file.exists(), "Test file should exist"

    # Verify the original file has a VBR header
    with open(test_file, 'rb') as f:
        parser = Mp3Parser(f)
        frames = list(parser)

    first_frame = frames[0]
    assert first_frame.has_vbr_header, "Test file should have VBR header"
    assert b'Xing' in first_frame.data, "Original frame should contain Xing header"

    # Test concatenation strips the VBR header
    concatenated_frames = list(concat_mp3_files([test_file]))
    assert len(concatenated_frames) > 0, "Should get frames from concatenation"

    first_concatenated_frame = concatenated_frames[0]
    assert b'Xing' not in first_concatenated_frame, "Concatenated frame should not contain Xing header"
    assert b'Info' not in first_concatenated_frame, "Concatenated frame should not contain Info header"
    assert b'VBRI' not in first_concatenated_frame, "Concatenated frame should not contain VBRI header"


if __name__ == "__main__":
    # Run tests directly if executed as script
    test_mp3_analysis()
    test_concat_mp3_files_success()
    test_frame_extraction_yields_valid_frames()
    test_vbr_header_stripping()
    print("All tests passed!")
