
"""
Voice Interface - Audio Input
Programming Design Project | Fall 2026

Purpose:
Record microphone audio and verify input functionality.
"""

import sounddevice as sd
import numpy as np


def list_devices():
    """Display available audio input/output devices."""

    print("Available Audio Devices:")
    print(sd.query_devices())


def record_audio(duration=5):
    """
    Record audio from the default microphone.

    Parameters:
        duration (int): Recording time in seconds.

    Returns:
        tuple: (audio data, sample rate), or None on error.
    """

    if duration <= 0:
        print("Error: Duration must be positive.")
        return None

    try:
        # Detect the default microphone settings
        microphone = sd.query_devices(kind="input")
        sample_rate = int(microphone["default_samplerate"])

        print("Microphone:", microphone["name"])
        print("Sample Rate:", sample_rate, "Hz")
        print("Recording for", duration, "seconds...")

        # Record microphone input
        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="float32"
        )

        # Wait until recording finishes
        sd.wait()

        print("Recording complete.")

        return recording, sample_rate

    except (sd.PortAudioError, ValueError) as error:
        print("Microphone error:", error)
        return None


def test_microphone():
    """Record, analyze, and replay microphone audio."""

    result = record_audio(5)

    if result is None:
        return

    recording, sample_rate = result

    # Calculate the RMS signal level
    rms = np.sqrt(np.mean(recording ** 2))

    print("RMS Audio Level:", round(float(rms), 4))

    if rms < 0.005:
        print("Warning: Audio level is very low.")
    else:
        print("Microphone signal detected.")

    # Play the recorded audio
    try:
        print("Playing recording...")
        sd.play(recording, samplerate=sample_rate)
        sd.wait()
        print("Playback completed.")

    except sd.PortAudioError as error:
        print("Playback error:", error)


if __name__ == "__main__":

    list_devices()
    test_microphone()
