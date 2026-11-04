"""Bounded, asynchronous PCM waveform envelopes for the controller display."""
import array
from dataclasses import dataclass
import sys
import wave


@dataclass(frozen=True)
class Envelope:
    frames: int
    peaks: tuple
    start: int = 0
    end: int | None = None


def read_envelope(path, columns=120, start=0, end=None):
    with wave.open(str(path), 'rb') as wav:
        width, channels, frames = wav.getsampwidth(), wav.getnchannels(), wav.getnframes()
        if width not in (1, 2, 3, 4) or channels not in (1, 2) or frames > 8*1024*1024:
            raise ValueError('unsupported or oversized display sample')
        start=max(0,min(frames,start));end=frames if end is None else max(start,min(frames,end))
        peaks = []
        for column in range(columns):
            first, last = start+(end-start)*column//columns, start+(end-start)*(column+1)//columns
            if first == last:
                peaks.append((0.0, 0.0))
                continue
            wav.setpos(first)
            data = wav.readframes(last-first)
            if width == 3:
                values = [int.from_bytes(data[i:i+3], 'little', signed=True) for i in range(0, len(data), 3)]
            else:
                values = array.array({1: 'B', 2: 'h', 4: 'i'}[width])
                values.frombytes(data)
                if width > 1 and sys.byteorder != 'little':
                    values.byteswap()
            if not values:
                peaks.append((0.0, 0.0))
                continue
            minimum, maximum = min(values), max(values)
            if width == 1:
                minimum -= 128
                maximum -= 128
            divisor = 1 << (width*8-1)
            peaks.append((minimum/divisor, maximum/divisor))
        return Envelope(frames, tuple(peaks),start,end)


class Waveforms:
    """Mikro uses the reusable PCM index, so zooming needs no new WAV read.

    Construction stays asynchronous in the low-priority index worker. The
    small view cache also avoids recomputing peaks during playhead refreshes.
    Import lazily because the index uses Envelope from this module.
    """
    def __init__(self):
        from app.mk3_waveforms import Mk3Waveforms
        self.indexed=Mk3Waveforms()

    def envelope(self,path,start=0,end=None):
        return self.indexed.envelope(path,start,end,columns=120)

    def close(self):self.indexed.close()
