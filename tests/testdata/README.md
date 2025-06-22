# Test Data for MP3 Utilities

This directory contains MP3 files used for testing the `glowtalk.mp3` module.

## Files

### Files WITHOUT bit reservoir (for concatenation testing)

- `test1.mp3` - 3.36 seconds, 140 frames, MPEG-2 24kHz mono VBR (no bit reservoir)
- `test2.mp3` - 3.70 seconds, 154 frames, MPEG-2 24kHz mono VBR (no bit reservoir)
- `test3.mp3` - 3.00 seconds, 125 frames, MPEG-2 24kHz mono VBR (no bit reservoir)

These files were generated using `lame --nores -V 1` to ensure they don't use the bit reservoir, making them suitable for concatenation testing.

### Files WITH bit reservoir (for validation testing)

- `test_with_bit_reservoir.mp3` - 3.36 seconds, 140 frames, MPEG-2 24kHz mono VBR (with bit reservoir)

This file uses the bit reservoir feature and is used to test that the concatenation function properly rejects such files.
