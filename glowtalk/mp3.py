"""Utilities for working with MP3 files."""

import pathlib
import struct
from typing import Iterable


def concat_mp3_files(input_paths: Iterable[pathlib.Path]) -> Iterable[bytes]:
    """Concatenate the given mp3 files.

    Reads each input path in turn, and yields `bytes` for the frames found.

    The mp3 files must all be encoded with independent frames (no bit reservoir). Raises an error if any frame uses the bit reservoir. This is
    key to making this low overhead enough to be done on demand for users.
    """
    for path in input_paths:
        # Check if file uses bit reservoir before processing
        _, _, _, _, uses_bit_reservoir = _analyze_mp3_frames(path)
        if uses_bit_reservoir:
            raise ValueError(f"File {path} uses bit reservoir and cannot be concatenated")

        # Yield frames from this file
        yield from _extract_mp3_frames(path)


def print_frame_info(path: pathlib.Path) -> None:
    """Print information about the MP3 frames in the given file."""
    try:
        frame_count, bitrates, mpeg_version, sample_rate, uses_bit_reservoir = _analyze_mp3_frames(path)

        print(f"File: {path}")
        print(f"Number of frames: {frame_count}")

        if sample_rate:
            # Calculate duration from frame count
            samples_per_frame = 1152 if mpeg_version == 1 else 576
            duration = (frame_count * samples_per_frame) / sample_rate
            print(f"Duration: {duration:.2f} seconds")
            print(f"Sample rate: {sample_rate} Hz")

        if mpeg_version:
            print(f"MPEG version: {mpeg_version}")

        print(f"Uses bit reservoir: {'Yes' if uses_bit_reservoir else 'No'}")

        if bitrates:
            min_bitrate = min(bitrates) * 1000  # Convert to bps
            max_bitrate = max(bitrates) * 1000  # Convert to bps
            avg_bitrate = sum(bitrates) / len(bitrates) * 1000  # Convert to bps

            if min_bitrate == max_bitrate:
                print(f"Bitrate mode: Constant (CBR)")
                print(f"Bitrate: {min_bitrate:.0f} bps")
            else:
                print(f"Bitrate mode: Variable (VBR)")
                print(f"Bitrate range: {min_bitrate:.0f} - {max_bitrate:.0f} bps")
                print(f"Average bitrate: {avg_bitrate:.0f} bps")
        else:
            print("Could not determine bitrate information")

    except Exception as e:
        print(f"Error reading MP3 file: {e}")


def _analyze_mp3_frames(path: pathlib.Path) -> tuple[int, list[int], int | None, int | None, bool]:
    """Analyze MP3 frames to get accurate count, bitrates, MPEG version, sample rate, and bit reservoir usage."""
    # MPEG bitrate table (kbps) - indexed by [version][layer][bitrate_index]
    bitrate_table = {
        1: {  # MPEG-1
            3: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]  # Layer III
        },
        2: {  # MPEG-2
            3: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]  # Layer III
        }
    }

    # Sample rate table - indexed by [version][sample_rate_index]
    sample_rate_table = {
        1: [44100, 48000, 32000],  # MPEG-1
        2: [22050, 24000, 16000],  # MPEG-2
        2.5: [11025, 12000, 8000]  # MPEG-2.5
    }

    frame_count = 0
    bitrates = []
    first_mpeg_version = None
    first_sample_rate = None
    uses_bit_reservoir = False

    try:
        with open(path, 'rb') as f:
            # Skip ID3v2 tag if present
            f.seek(0)
            header = f.read(10)
            if header.startswith(b'ID3'):
                # Parse ID3v2 header to skip it
                size = struct.unpack('>I', header[6:10])[0]
                # ID3v2 size is synchsafe integer
                size = ((size & 0x7f000000) >> 3) | ((size & 0x007f0000) >> 2) | ((size & 0x00007f00) >> 1) | (size & 0x0000007f)
                f.seek(size + 10)
            else:
                f.seek(0)

            while True:
                # Look for frame sync (11 bits set)
                data = f.read(4)
                if len(data) < 4:
                    break

                # Check for MP3 frame header
                if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
                    # Parse header
                    version_bits = (data[1] & 0x18) >> 3
                    layer_bits = (data[1] & 0x06) >> 1
                    protection_bit = (data[1] & 0x01)
                    bitrate_index = (data[2] & 0xF0) >> 4
                    sample_rate_index = (data[2] & 0x0C) >> 2
                    padding = (data[2] & 0x02) >> 1
                    private_bit = (data[2] & 0x01)
                    channel_mode = (data[3] & 0xC0) >> 6
                    mode_extension = (data[3] & 0x30) >> 4
                    copyright = (data[3] & 0x08) >> 3
                    original = (data[3] & 0x04) >> 2
                    emphasis = (data[3] & 0x03)

                    # Map version bits to MPEG version
                    if version_bits == 3:
                        mpeg_version = 1  # MPEG-1
                    elif version_bits == 2:
                        mpeg_version = 2  # MPEG-2
                    elif version_bits == 0:
                        mpeg_version = 2.5  # MPEG-2.5
                    else:
                        # Skip non-standard frames
                        f.seek(-3, 1)
                        continue

                    # Map layer bits (3 = Layer I, 2 = Layer II, 1 = Layer III)
                    layer = 4 - layer_bits

                    # We only handle Layer III (MP3)
                    if layer == 3 and mpeg_version in [1, 2] and bitrate_index < 16:
                        bitrate = bitrate_table[mpeg_version][layer][bitrate_index]
                        if bitrate > 0 and sample_rate_index < 3:  # Valid bitrate and sample rate
                            # Read side information to get main data begin
                            side_info_size = 17 if channel_mode == 3 else 32  # mono vs stereo
                            if protection_bit == 0:  # CRC present
                                side_info_size += 2

                            side_info_data = f.read(side_info_size)
                            if len(side_info_data) >= side_info_size:
                                # Parse main data begin from side information
                                # It's in the first 9 bits after CRC (if present)
                                crc_offset = 2 if protection_bit == 0 else 0
                                if len(side_info_data) > crc_offset + 1:
                                    # Main data begin is 9 bits starting from the first byte of side info
                                    main_data_begin = ((side_info_data[crc_offset] << 1) |
                                                     (side_info_data[crc_offset + 1] >> 7)) & 0x1FF

                                    if main_data_begin > 0:
                                        uses_bit_reservoir = True

                                frame_count += 1
                                bitrates.append(bitrate)

                                # Store first frame's metadata
                                if first_mpeg_version is None:
                                    first_mpeg_version = mpeg_version
                                    first_sample_rate = sample_rate_table[mpeg_version][sample_rate_index]

                                # Calculate frame size to skip to next frame
                                sample_rate = sample_rate_table[mpeg_version][sample_rate_index]
                                samples_per_frame = 1152 if mpeg_version == 1 else 576
                                frame_size = int((samples_per_frame * bitrate * 1000 / 8) / sample_rate) + padding
                                # Skip remaining frame data (we already read header + side info)
                                remaining_size = frame_size - 4 - side_info_size
                                if remaining_size > 0:
                                    f.seek(remaining_size, 1)
                            else:
                                f.seek(-3, 1)
                        else:
                            f.seek(-3, 1)
                    else:
                        f.seek(-3, 1)
                else:
                    f.seek(-3, 1)

    except Exception:
        # If frame parsing fails, return what we have
        pass

    return frame_count, bitrates, first_mpeg_version, first_sample_rate, uses_bit_reservoir


def _extract_mp3_frames(path: pathlib.Path) -> Iterable[bytes]:
    """Extract MP3 frames from a file and yield them as bytes."""
    # MPEG bitrate table (kbps) - indexed by [version][layer][bitrate_index]
    bitrate_table = {
        1: {  # MPEG-1
            3: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]  # Layer III
        },
        2: {  # MPEG-2
            3: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]  # Layer III
        }
    }

    # Sample rate table - indexed by [version][sample_rate_index]
    sample_rate_table = {
        1: [44100, 48000, 32000],  # MPEG-1
        2: [22050, 24000, 16000],  # MPEG-2
        2.5: [11025, 12000, 8000]  # MPEG-2.5
    }

    with open(path, 'rb') as f:
        # Skip ID3v2 tag if present
        f.seek(0)
        header = f.read(10)
        if header.startswith(b'ID3'):
            # Parse ID3v2 header to skip it
            size = struct.unpack('>I', header[6:10])[0]
            # ID3v2 size is synchsafe integer
            size = ((size & 0x7f000000) >> 3) | ((size & 0x007f0000) >> 2) | ((size & 0x00007f00) >> 1) | (size & 0x0000007f)
            f.seek(size + 10)
        else:
            f.seek(0)

        while True:
            # Look for frame sync (11 bits set)
            frame_start_pos = f.tell()
            data = f.read(4)
            if len(data) < 4:
                break

            # Check for MP3 frame header
            if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
                # Parse header
                version_bits = (data[1] & 0x18) >> 3
                layer_bits = (data[1] & 0x06) >> 1
                protection_bit = (data[1] & 0x01)
                bitrate_index = (data[2] & 0xF0) >> 4
                sample_rate_index = (data[2] & 0x0C) >> 2
                padding = (data[2] & 0x02) >> 1
                channel_mode = (data[3] & 0xC0) >> 6

                # Map version bits to MPEG version
                if version_bits == 3:
                    mpeg_version = 1  # MPEG-1
                elif version_bits == 2:
                    mpeg_version = 2  # MPEG-2
                elif version_bits == 0:
                    mpeg_version = 2.5  # MPEG-2.5
                else:
                    # Skip non-standard frames
                    f.seek(-3, 1)
                    continue

                # Map layer bits (3 = Layer I, 2 = Layer II, 1 = Layer III)
                layer = 4 - layer_bits

                # We only handle Layer III (MP3)
                if layer == 3 and mpeg_version in [1, 2] and bitrate_index < 16:
                    bitrate = bitrate_table[mpeg_version][layer][bitrate_index]
                    if bitrate > 0 and sample_rate_index < 3:  # Valid bitrate and sample rate
                        # Calculate frame size
                        sample_rate = sample_rate_table[mpeg_version][sample_rate_index]
                        samples_per_frame = 1152 if mpeg_version == 1 else 576
                        frame_size = int((samples_per_frame * bitrate * 1000 / 8) / sample_rate) + padding

                        # Go back to start of frame and read the entire frame
                        f.seek(frame_start_pos)
                        frame_data = f.read(frame_size)

                        if len(frame_data) == frame_size:
                            yield frame_data
                        else:
                            # Incomplete frame, end of file
                            break
                    else:
                        f.seek(-3, 1)
                else:
                    f.seek(-3, 1)
            else:
                f.seek(-3, 1)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <mp3 file> # for info")
        print("   or:  mp3_concat.py <mp3 file1> <mp3 file2> ... > output.mp3 # to concatenate")
        sys.exit(1)

    if len(sys.argv) == 2:
        mp3_path = pathlib.Path(sys.argv[1])
        if not mp3_path.is_file():
            print(f"Error: {mp3_path} is not a valid file.")
            sys.exit(1)
        print_frame_info(mp3_path)

    mp3_paths = [pathlib.Path(arg) for arg in sys.argv[1:]]
    for bytes in concat_mp3_files(mp3_paths):
        sys.stdout.buffer.write(bytes)

