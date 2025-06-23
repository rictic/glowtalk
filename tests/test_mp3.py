"""Tests for MP3 utilities.

Run like:
  python -m pytest tests/test_mp3.py

Or run `pytest` in the `glowtalk` directory to run all tests.
"""

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

    # Frame count may be less than sum of all frames due to LAME padding removal
    assert frame_count <= sum(expected_frames), "Concatenated frames should be less than or equal to all frames"
    assert frame_count > 0, "Should get some frames from concatenation"
    # Note: total_bytes will be less than file sizes due to ID3 tags being stripped
    assert total_bytes > 0, "Should have some data"
    # Calculate the sha256 of the concatenated data for verification
    sha256 = hashlib.sha256()
    for frame_data in concat_mp3_files(test_files):
        sha256.update(frame_data)
    digest = sha256.hexdigest()
    # Updated hash reflecting LAME padding frame removal
    expected_digest = "37f23c8f2d088212fe76622346e6a20ebcd8441dcee9533ff5a6b09b692e707b"
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


def test_compatibility_checking():
    """Test that concatenation validates file compatibility."""
    # Test with compatible files (should work)
    compatible_files = [
        pathlib.Path("tests/testdata/test1.mp3"),
        pathlib.Path("tests/testdata/test2.mp3")
    ]

    # This should work without issues
    concatenated_frames = list(concat_mp3_files(compatible_files))
    assert len(concatenated_frames) > 0, "Should successfully concatenate compatible files"

    # Test with ID3-tagged file that has compatible encoding
    id3_file = pathlib.Path("tests/testdata/test_24khz_with_id3.mp3")
    if id3_file.exists():
        mixed_files = [
            pathlib.Path("tests/testdata/test1.mp3"),
            id3_file
        ]
        concatenated_frames = list(concat_mp3_files(mixed_files))
        assert len(concatenated_frames) > 0, "Should concatenate compatible files even with ID3 tags"


def test_incompatible_sample_rates():
    """Test that concatenation fails when files have different sample rates."""
    test_file_24khz = pathlib.Path("tests/testdata/test1.mp3")  # 24kHz
    test_file_22khz = pathlib.Path("tests/testdata/test_22khz.mp3")  # 22kHz

    assert test_file_24khz.exists(), "24kHz test file should exist"
    assert test_file_22khz.exists(), "22kHz test file should exist"

    with pytest.raises(ValueError, match="sample rate"):
        list(concat_mp3_files([test_file_24khz, test_file_22khz]))


def test_id3_tag_handling():
    """Test that files with ID3 tags are handled correctly."""
    test_file_with_id3 = pathlib.Path("tests/testdata/test_24khz_with_id3.mp3")

    if not test_file_with_id3.exists():
        pytest.skip("ID3 test file not available")

    # Should concatenate successfully despite having ID3 tags
    concatenated_frames = list(concat_mp3_files([test_file_with_id3]))
    assert len(concatenated_frames) > 0, "Should successfully handle files with ID3 tags"


def test_lame_padding_frame_stripping():
    """Test that LAME padding frames are stripped during concatenation."""
    test_file = pathlib.Path("tests/testdata/test1.mp3")
    assert test_file.exists(), "Test file should exist"

    # Parse frames directly to see original count including padding
    with open(test_file, 'rb') as f:
        parser = Mp3Parser(f)
        all_frames = list(parser)

    # Get concatenated frames (should have padding stripped)
    concatenated_frames = list(concat_mp3_files([test_file]))

    # Concatenated frames should be less than or equal to all frames
    # (due to potential LAME padding frame removal)
    assert len(concatenated_frames) <= len(all_frames), "Concatenation should strip padding frames"

    # Verify no concatenated frames are tiny LAME padding frames
    for frame_data in concatenated_frames:
        if len(frame_data) <= 32 and b'LAME' in frame_data:
            pytest.fail("Concatenated output should not contain LAME padding frames")


def test_cbr_file_rejection():
    """Test that CBR files with bit reservoir are properly rejected."""
    cbr_file = pathlib.Path("tests/testdata/test_cbr_with_id3.mp3")

    if not cbr_file.exists():
        pytest.skip("CBR test file not available")

    with pytest.raises(ValueError, match="uses bit reservoir"):
        list(concat_mp3_files([cbr_file]))


def test_stereo_file_compatibility():
    """Test that stereo files without bit reservoir can be concatenated."""
    stereo_file = pathlib.Path("tests/testdata/test_stereo_nores.mp3")

    if not stereo_file.exists():
        pytest.skip("Stereo test file not available")

    # Should work since it's encoded without bit reservoir
    concatenated_frames = list(concat_mp3_files([stereo_file]))
    assert len(concatenated_frames) > 0, "Should successfully concatenate stereo files without bit reservoir"
