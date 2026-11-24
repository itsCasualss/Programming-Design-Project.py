
"""
10/28/2026

Voice Interface - Audio Input

audio_input.py will record the audio from the defaulted microphone connected.
"""

import sounddevice as sd

def record_audio(duration=3, sample_rate=16000):
    #Recording the Auido input for 5 secs, sets sample rate to match Vosk package of 16k Hz 

    print("Listening...")

    recording = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32"
    )

    sd.wait()

    return recording, sample_rate

def main():
    """Test microphone recording and playback."""

    audio, sample_rate = record_audio()

    print("Playing recording...")

    sd.play(audio, samplerate=sample_rate)
    sd.wait()


if __name__ == "__main__":
    main()
