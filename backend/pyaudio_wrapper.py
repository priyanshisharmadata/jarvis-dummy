"""
sounddevice-based PyAudio wrapper
=================================

A drop-in replacement for the ``pyaudio`` package that uses ``sounddevice``
under the hood.  No C++ build tools or wheel compilation needed — just
install ``sounddevice`` and ``numpy`` from PyPI.

.. note::
    This wrapper exposes the subset of the PyAudio API that Jarvis actually
    uses::

        * ``PyAudio``          – stream factory
        * ``Stream``           – read / stop / close
        * ``paInt16``          – format constants
        * ``get_sample_size``  – byte size of a format

Using the wrapper
-----------------
Append this block at the top of any module that does ``import pyaudio``:

.. code-block:: python

    try:
        import pyaudio
    except ImportError:
        from backend import pyaudio_wrapper  # noqa: F401 – monkey-patches sys.modules
        import pyaudio  # now resolves to this wrapper
"""

import sys
import numpy as np

# -- Format constants matching the real PyAudio definitions ---------------
paInt16 = 2
paInt32 = 8


def get_sample_size(fmt: int) -> int:
    """Return the size in bytes of a single sample in the given format."""
    if fmt == paInt16:
        return 2
    if fmt == paInt32:
        return 4
    return 2  # sensible default


# -- PyAudio -------------------------------------------------------------


class PyAudio:
    """Minimal PyAudio-compatible interface backed by ``sounddevice``."""

    def __init__(self) -> None:
        self._streams: list = []
        try:
            self._devices = sd.query_devices()
        except Exception:
            self._devices = []

    # ---------- Device helpers ------------------------------------------

    def get_device_count(self) -> int:
        """Return the number of available audio devices (>= 1)."""
        return max(len(self._devices), 1)

    def get_default_input_device_info(self) -> dict:
        """Dictionary with *index*, *name*, *maxInputChannels*,
        *defaultSampleRate* for the current default input device."""
        try:
            idx = sd.default.device[0]
            if idx is None or idx < 0:
                idx = 0
            dev = sd.query_devices()[idx]
            return {
                "index": idx,
                "name": dev["name"],
                "maxInputChannels": dev["max_input_channels"],
                "defaultSampleRate": int(dev.get("default_samplerate", 44100)),
            }
        except Exception:
            return {
                "index": 0,
                "name": "default",
                "maxInputChannels": 1,
                "defaultSampleRate": 44100,
            }

    def get_device_info_by_index(self, index: int | None) -> dict:
        """Same shape as ``get_default_input_device_info`` but for *index*.

        If *index* is ``None`` the default device is returned.
        """
        if index is None:
            return self.get_default_input_device_info()
        try:
            dev = sd.query_devices()[index]
            return {
                "index": index,
                "name": dev["name"],
                "maxInputChannels": dev["max_input_channels"],
                "defaultSampleRate": int(dev.get("default_samplerate", 44100)),
            }
        except Exception:
            return self.get_default_input_device_info()

    # ---------- Stream factory ------------------------------------------

    def open(
        self,
        rate: int | None = None,
        channels: int | None = None,
        format: int | None = None,
        input: bool | None = None,
        frames_per_buffer: int | None = None,
        input_device_index: int | None = None,
        **kwargs,
    ):
        """Open an input ``Stream`` with the given parameters.

        Returns
        -------
        Stream
            Wrapper around a ``sounddevice.InputStream``.
        """
        samplerate = rate or 44100
        ch = channels or 1
        dtype = "int16" if (format is None or format == paInt16) else "int32"
        blocksize = frames_per_buffer or 1024

        # Prevent "index out of range" when the caller passes an invalid device index
        device = input_device_index
        device_count = self.get_device_count()
        if device is not None and device >= device_count:
            print(
                f"[pyaudio_wrapper] Device index {device} out of range "
                f"(max {device_count - 1}); falling back to default device"
            )
            device = None

        stream = sd.InputStream(
            samplerate=samplerate,
            channels=ch,
            dtype=dtype,
            blocksize=blocksize,
            device=device,
        )
        self._streams.append(stream)
        stream.start()
        return Stream(stream, blocksize, format)

    # ---------- Cleanup -------------------------------------------------

    def terminate(self) -> None:
        """Stop and discard all streams created by this PyAudio instance."""
        for s in self._streams:
            try:
                s.stop()
            except Exception:
                pass
        self._streams.clear()


# -- Stream --------------------------------------------------------------


class Stream:
    """Wrapper around ``sounddevice.InputStream`` with a ``read`` method.

    Implements the subset of the PyAudio ``Stream`` API that Jarvis needs:
    ``read``, ``is_stopped``, ``stop_stream``, and ``close``.
    """

    def __init__(self, stream, chunk_size: int, fmt: int) -> None:
        self._stream = stream
        self._chunk = chunk_size
        self._format = fmt
        self._stopped = False

    def read(self, num_frames: int, exception_on_overflow: bool = False) -> bytes:
        """Read *num_frames* of audio data.

        Returns
        -------
        bytes
            Raw PCM audio bytes.
        """
        try:
            data, _ = self._stream.read(num_frames)
            return data.tobytes()
        except sd.CallbackStop:
            # Return silence instead of crashing
            sample_size = get_sample_size(self._format)
            return b"\x00" * (num_frames * sample_size)

    def is_stopped(self) -> bool:
        """Return ``True`` if the stream has been actively stopped."""
        return self._stopped

    def stop_stream(self) -> None:
        """Signal the stream to stop."""
        self._stopped = True
        try:
            self._stream.stop()
        except Exception:
            pass

    def close(self) -> None:
        """Stop and release the underlying stream."""
        try:
            self._stream.stop()
        except Exception:
            pass


# ------------------------------------------------------------------------
# Monkey-patch ``sys.modules`` so that ``import pyaudio`` resolves to this
# wrapper when the real ``pyaudio`` is not installed.
# ------------------------------------------------------------------------
try:
    import pyaudio  # noqa: F401
except ImportError:
    import sounddevice as sd

    fake_module = type(sys)("pyaudio")
    fake_module.PyAudio = PyAudio
    fake_module.paInt16 = paInt16
    fake_module.paInt32 = paInt32
    fake_module.get_sample_size = get_sample_size
    fake_module.get_device_count = lambda: 1
    sys.modules["pyaudio"] = fake_module
    print("PyAudio wrapper (sounddevice) loaded successfully")
