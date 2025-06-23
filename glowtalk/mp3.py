"""Utilities for working with MP3 files."""

import pathlib
import struct

from typing import BinaryIO, Generator, NamedTuple, Sequence


def concat_mp3_files(input_paths: Sequence[pathlib.Path]) -> Generator[bytes]:
    """Concatenate the given mp3 files.

    Reads each input path in turn, and yields `bytes` for the frames found.

    The mp3 files must all be encoded with independent frames (no bit reservoir).
    Raises an error if any frame uses the bit reservoir. This is key to making this
    low overhead enough to be done on demand for users.

    All files should have the same MPEG version, sample rate,
    and channel mode.

    Note: VBR headers (Xing/LAME) are stripped from the first frame to prevent duration
    metadata issues in concatenated files. This may cause some players to initially
    show incorrect duration until they scan the full file.

    This function works in streaming mode - it processes files one at a time and can
    handle lazy iterables that are only available as needed.
    """
    expected_mpeg_version = None
    expected_sample_rate = None
    expected_channel_mode = None
    first_frame = True

    for path in input_paths:
        with open(path, "rb") as f:
            parser = Mp3Parser(f)

            for frame in parser:
                if frame.uses_bit_reservoir:
                    raise ValueError(
                        f"File {path} uses bit reservoir and cannot be concatenated"
                    )

                # Check compatibility with previous files
                if first_frame:
                    expected_mpeg_version = frame.mpeg_version
                    expected_sample_rate = frame.sample_rate
                    expected_channel_mode = frame.channel_mode
                    first_frame = False
                else:
                    if frame.mpeg_version != expected_mpeg_version:
                        raise ValueError(
                            f"File {path} has MPEG version {frame.mpeg_version}, "
                            f"expected {expected_mpeg_version}"
                        )
                    if frame.sample_rate != expected_sample_rate:
                        raise ValueError(
                            f"File {path} has sample rate {frame.sample_rate} Hz, "
                            f"expected {expected_sample_rate} Hz"
                        )
                    if frame.channel_mode != expected_channel_mode:
                        import warnings

                        warnings.warn(
                            f"File {path} has different channel mode {frame.channel_mode}, "
                            f"expected {expected_channel_mode}. Concatenation may cause audio artifacts."
                        )

                frame_data = frame.data

                # Strip VBR headers, they contain metadata that becomes
                # incorrect when concatenating files.
                if frame.has_vbr_header:
                    frame_data = _strip_vbr_header(frame_data)

                # Strip LAME padding frames if present
                if _strip_lame_padding_frame(frame_data):
                    continue

                yield frame_data


def print_frame_info(path: pathlib.Path) -> None:
    """Print information about the MP3 frames in the given file."""
    try:
        with open(path, "rb") as f:
            parser = Mp3Parser(f)

            frames = list(parser)
            if not frames:
                print(f"File: {path}")
                print("No valid MP3 frames found")
                return

            frame_count = len(frames)
            bitrates = [frame.bitrate for frame in frames]
            first_frame = frames[0]
            uses_bit_reservoir = any(frame.uses_bit_reservoir for frame in frames)

            print(f"File: {path}")
            print(f"Number of frames: {frame_count}")

            # Calculate duration from frame count
            total_duration = sum(frame.duration_seconds for frame in frames)
            print(f"Duration: {total_duration:.2f} seconds")
            print(f"Sample rate: {first_frame.sample_rate} Hz")
            print(f"MPEG version: {first_frame.mpeg_version}")

            print(f"Uses bit reservoir: {'Yes' if uses_bit_reservoir else 'No'}")

            if bitrates:
                min_bitrate = min(bitrates) * 1000  # Convert to bps
                max_bitrate = max(bitrates) * 1000  # Convert to bps
                avg_bitrate = sum(bitrates) / len(bitrates) * 1000  # Convert to bps

                if min_bitrate == max_bitrate:
                    print("Bitrate mode: Constant (CBR)")
                    print(f"Bitrate: {min_bitrate:.0f} bps")
                else:
                    print("Bitrate mode: Variable (VBR)")
                    print(f"Bitrate range: {min_bitrate:.0f} - {max_bitrate:.0f} bps")
                    print(f"Average bitrate: {avg_bitrate:.0f} bps")
            else:
                print("Could not determine bitrate information")

    except Exception as e:
        print(f"Error reading MP3 file: {e}")


def _strip_vbr_header(frame_data: bytes) -> bytes:
    """Strip VBR header (Xing/LAME/VBRI) from an MP3 frame if present.

    VBR headers contain metadata about the entire file (frame count, duration, etc.)
    which becomes incorrect when concatenating files. Removing them forces players
    to scan the entire file for accurate duration.
    """
    if len(frame_data) < 40:  # Too small to have VBR header
        return frame_data

    # Parse MP3 header to find where side info ends and main data begins
    version_bits = (frame_data[1] & 0x18) >> 3
    channel_mode = (frame_data[3] & 0xC0) >> 6
    protection_bit = frame_data[1] & 0x01

    # Calculate side info size
    if version_bits == 3:  # MPEG-1
        side_info_size = 17 if channel_mode == 3 else 32  # mono vs stereo
    else:  # MPEG-2/2.5
        side_info_size = 9 if channel_mode == 3 else 17  # mono vs stereo

    if protection_bit == 0:  # CRC present
        side_info_size += 2

    # Main data starts after: 4-byte header + side_info_size
    main_data_offset = 4 + side_info_size

    if len(frame_data) <= main_data_offset + 8:
        return frame_data

    # Check for VBR headers at the start of main data
    main_data_start = main_data_offset

    # Check for Xing/Info header
    if frame_data[main_data_start : main_data_start + 4] in [b"Xing", b"Info"]:
        # Xing header found - replace with silence/zeros
        # Xing header is typically 120 bytes
        header_size = min(120, len(frame_data) - main_data_start)

        # Check if LAME header follows immediately after Xing
        lame_offset = main_data_start + 120
        if (
            lame_offset + 4 <= len(frame_data)
            and frame_data[lame_offset : lame_offset + 4] == b"LAME"
        ):
            # LAME header is 36 bytes, include it in stripping
            header_size = min(156, len(frame_data) - main_data_start)  # 120 + 36

        return (
            frame_data[:main_data_start]
            + b"\x00" * header_size
            + frame_data[main_data_start + header_size :]
        )

    # Check for VBRI header (alternative VBR header format)
    elif frame_data[main_data_start : main_data_start + 4] == b"VBRI":
        # VBRI header found - replace with silence
        header_size = min(
            26, len(frame_data) - main_data_start
        )  # VBRI header is 26 bytes
        return (
            frame_data[:main_data_start]
            + b"\x00" * header_size
            + frame_data[main_data_start + header_size :]
        )

    # No VBR header found, return original frame
    return frame_data


def _strip_lame_padding_frame(frame_data: bytes) -> bool:
    """Check if this is a LAME padding frame that should be stripped.

    LAME often adds padding frames at the end of files with minimal audio data.
    These frames typically contain mostly the LAME encoder signature.

    Returns True if this frame should be stripped during concatenation.
    """
    # Look for LAME signature in various positions within the frame
    if b"LAME3.100" in frame_data:
        # Check if this is a very short frame (likely padding)
        if len(frame_data) <= 32:
            return True

        # Check if most of the frame is zeros or LAME signature
        non_header_data = frame_data[4:]  # Skip MP3 header
        lame_content = non_header_data.count(b"LAME3.100") * 9  # Length of "LAME3.100"
        zero_content = non_header_data.count(0)

        # If more than 80% of the frame is LAME signatures or zeros, it's likely padding
        if (lame_content + zero_content) > (len(non_header_data) * 0.8):
            return True

    return False


class Mp3Frame(NamedTuple):
    """Structured representation of an MP3 frame."""

    data: bytes
    mpeg_version: int
    layer: int
    sample_rate: int
    bitrate: int  # in kbps
    channel_mode: int
    frame_size: int
    uses_bit_reservoir: bool
    has_vbr_header: bool

    @property
    def duration_seconds(self) -> float:
        """Calculate the duration of this frame in seconds."""
        samples_per_frame = 1152 if self.mpeg_version == 1 else 576
        return samples_per_frame / self.sample_rate


class Mp3Parser:
    """Parser for MP3 files that yields structured frame objects."""

    # MPEG bitrate table (kbps) - indexed by [version][layer][bitrate_index]
    BITRATE_TABLE = {
        1: {  # MPEG-1
            3: [
                0,
                32,
                40,
                48,
                56,
                64,
                80,
                96,
                112,
                128,
                160,
                192,
                224,
                256,
                320,
                0,
            ]  # Layer III
        },
        2: {  # MPEG-2
            3: [
                0,
                8,
                16,
                24,
                32,
                40,
                48,
                56,
                64,
                80,
                96,
                112,
                128,
                144,
                160,
                0,
            ]  # Layer III
        },
    }

    # Sample rate table - indexed by [version][sample_rate_index]
    SAMPLE_RATE_TABLE = {
        1: [44100, 48000, 32000],  # MPEG-1
        2: [22050, 24000, 16000],  # MPEG-2
        2.5: [11025, 12000, 8000],  # MPEG-2.5
    }

    def __init__(self, file: BinaryIO):
        self.file = file
        self._skip_id3v2_tag()

    def _skip_id3v2_tag(self) -> None:
        """Skip ID3v2 tag if present."""
        self.file.seek(0)
        header = self.file.read(10)
        if header.startswith(b"ID3"):
            # Parse ID3v2 header to skip it
            size = struct.unpack(">I", header[6:10])[0]
            # ID3v2 size is synchsafe integer
            size = (
                ((size & 0x7F000000) >> 3)
                | ((size & 0x007F0000) >> 2)
                | ((size & 0x00007F00) >> 1)
                | (size & 0x0000007F)
            )
            self.file.seek(size + 10)
        else:
            self.file.seek(0)

    def _check_vbr_header(self, frame_data: bytes, main_data_offset: int) -> bool:
        """Check if frame contains VBR header."""
        if len(frame_data) <= main_data_offset + 4:
            return False

        main_data_start = main_data_offset
        return frame_data[main_data_start : main_data_start + 4] in [
            b"Xing",
            b"Info",
            b"VBRI",
        ]

    def _parse_main_data_begin(
        self,
        frame_data: bytes,
        protection_bit: int,
        channel_mode: int,
        mpeg_version: int,
    ) -> bool:
        """Parse main data begin field to check for bit reservoir usage."""
        # Calculate side info size
        if mpeg_version == 1:  # MPEG-1
            side_info_size = 17 if channel_mode == 3 else 32  # mono vs stereo
        else:  # MPEG-2/2.5
            side_info_size = 9 if channel_mode == 3 else 17  # mono vs stereo
        if protection_bit == 0:  # CRC present
            side_info_size += 2

        if len(frame_data) <= 4 + side_info_size:
            return False

        crc_offset = 2 if protection_bit == 0 else 0
        side_info_start = 4 + crc_offset

        if len(frame_data) <= side_info_start + 1:
            return False

        # Main data begin is 9 bits starting from the first byte of side info
        main_data_begin = (
            (frame_data[side_info_start] << 1) | (frame_data[side_info_start + 1] >> 7)
        ) & 0x1FF

        return main_data_begin > 0

    def __iter__(self) -> Generator[Mp3Frame]:
        """Iterate over MP3 frames in the file."""
        while True:
            # Look for frame sync (11 bits set)
            frame_start_pos = self.file.tell()
            data = self.file.read(4)
            if len(data) < 4:
                break

            # Check for MP3 frame header
            if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
                # Parse header
                version_bits = (data[1] & 0x18) >> 3
                layer_bits = (data[1] & 0x06) >> 1
                protection_bit = data[1] & 0x01
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
                    self.file.seek(-3, 1)
                    continue

                # Map layer bits (3 = Layer I, 2 = Layer II, 1 = Layer III)
                layer = 4 - layer_bits

                # We only handle Layer III (MP3)
                if (
                    layer == 3
                    and mpeg_version in [1, 2]
                    and bitrate_index < 16
                    and sample_rate_index < 3
                ):
                    assert isinstance(mpeg_version, int)

                    bitrate = self.BITRATE_TABLE[mpeg_version][layer][bitrate_index]
                    sample_rate = self.SAMPLE_RATE_TABLE[mpeg_version][
                        sample_rate_index
                    ]

                    if bitrate > 0:  # Valid bitrate
                        # Calculate frame size
                        samples_per_frame = 1152 if mpeg_version == 1 else 576
                        frame_size = (
                            int((samples_per_frame * bitrate * 1000 / 8) / sample_rate)
                            + padding
                        )

                        # Go back to start of frame and read the entire frame
                        self.file.seek(frame_start_pos)
                        frame_data = self.file.read(frame_size)

                        if len(frame_data) == frame_size:
                            # Check for bit reservoir usage
                            uses_bit_reservoir = self._parse_main_data_begin(
                                frame_data, protection_bit, channel_mode, mpeg_version
                            )

                            # Check for VBR header
                            if mpeg_version == 1:  # MPEG-1
                                side_info_size = 17 if channel_mode == 3 else 32
                            else:  # MPEG-2/2.5
                                side_info_size = 9 if channel_mode == 3 else 17
                            if protection_bit == 0:
                                side_info_size += 2
                            main_data_offset = 4 + side_info_size
                            has_vbr_header = self._check_vbr_header(
                                frame_data, main_data_offset
                            )

                            yield Mp3Frame(
                                data=frame_data,
                                mpeg_version=mpeg_version,
                                layer=layer,
                                sample_rate=sample_rate,
                                bitrate=bitrate,
                                channel_mode=channel_mode,
                                frame_size=frame_size,
                                uses_bit_reservoir=uses_bit_reservoir,
                                has_vbr_header=has_vbr_header,
                            )
                        else:
                            # Incomplete frame, end of file
                            break
                    else:
                        self.file.seek(-3, 1)
                else:
                    self.file.seek(-3, 1)
            else:
                self.file.seek(-3, 1)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <mp3 file> # for info")
        print(
            "   or:  mp3_concat.py <mp3 file1> <mp3 file2> ... > output.mp3 # to concatenate"
        )
        sys.exit(1)

    if len(sys.argv) == 2:
        mp3_path = pathlib.Path(sys.argv[1])
        if not mp3_path.is_file():
            print(f"Error: {mp3_path} is not a valid file.")
            sys.exit(1)
        print_frame_info(mp3_path)
        sys.exit(0)

    mp3_paths = [pathlib.Path(arg) for arg in sys.argv[1:]]
    for bytes in concat_mp3_files(mp3_paths):
        sys.stdout.buffer.write(bytes)
