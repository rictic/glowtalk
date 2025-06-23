# Test Data for MP3 Utilities

This directory contains MP3 files used for testing the `glowtalk.mp3` module.

## Files

### Compatible Files (no bit reservoir, 24kHz MPEG-2)

- `test1.mp3`: 3.36s, 140 frames, MPEG-2 24kHz mono VBR, no bit reservoir, with Xing header
- `test2.mp3`: 3.70s, 154 frames, MPEG-2 24kHz mono VBR, no bit reservoir, with Xing header
- `test3.mp3`: 3.00s, 125 frames, MPEG-2 24kHz mono VBR, no bit reservoir, with Xing header
- `test_24khz_with_id3.mp3`: 1.08s, 45 frames, MPEG-2 24kHz mono VBR, no bit reservoir, ID3v1+v2 tags
- `test_stereo_nores.mp3`: 1.08s, 45 frames, MPEG-2 24kHz stereo VBR, no bit reservoir

### Incompatible Files (various reasons)

- `test_with_bit_reservoir.mp3`: 3.36s, 140 frames, MPEG-2 24kHz mono VBR, **WITH bit reservoir** (cannot concatenate)
- `test_cbr_with_id3.mp3`: 1.07s, 41 frames, MPEG-1 44kHz mono CBR 128kbps, **WITH bit reservoir**, ID3v1+v2 tags (cannot concatenate)
- `test_22khz.mp3`: 1.00s, 41 frames, MPEG-2 **22kHz** mono VBR, no bit reservoir (incompatible sample rate)
- `test_abr.mp3`: 1.00s, 40 frames, MPEG-1 **44kHz** mono ABR ~70kbps average (incompatible sample rate)
