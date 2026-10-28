
"""

HEAVILY UTILITZED AI, Current time: 0259hrs 10/28/26
Runs as anticipated however,

ISSUES:
Multiple commands being stated cause error, need to solve this by including another if statement. 


Voice Interface - Speech Recognition
Recognizes four voice commands using Vosk.
"""

import json
from pathlib import Path

import numpy as np
from vosk import Model, KaldiRecognizer

try:
    from audio_input import record_audio
except ImportError:
    from audio_input import record_audio


# Supported voice commands
COMMANDS = {
    "schedule": ["schedule", "my schedule", "show my schedule"],
    "pills": ["pills", "my pills", "medication"],
    "weather": ["weather", "the weather", "tell me the weather"],
    "news": ["news", "the news", "tell me the news"]
}

# Numbered menu options
OPTIONS = {
    "one": "schedule",
    "two": "pills",
    "three": "weather",
    "four": "news"
}

# Location of Vosk model
MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "assets/models/vosk-model-small-en-us-0.15"
)


def parse_command(text):
    """Identify the requested command from recognized speech."""

    words = text.lower().replace("[unk]", "").split()

    # Convert numeric digits to words
    digits = {"1": "one", "2": "two", "3": "three", "4": "four"}
    words = [digits.get(word, word) for word in words]

    matches = set()

    # Identify command keywords
    for command, phrases in COMMANDS.items():
        keywords = {word for phrase in phrases for word in phrase.split()
                    if word in ("schedule", "pills", "medication",
                                "weather", "news")}

        if any(word in keywords for word in words):
            matches.add(command)

    # Identify numbered options
    for i, word in enumerate(words):
        if word in ("option", "number") and i + 1 < len(words):
            choice = OPTIONS.get(words[i + 1])
            if choice:
                matches.add(choice)

    # Allow a standalone number
    if len(words) == 1 and words[0] in OPTIONS:
        matches.add(OPTIONS[words[0]])

    # Return only if one unique command was identified
    return matches.pop() if len(matches) == 1 else None


def recognize_command(model):
    """Record audio and recognize a spoken command."""

    audio, sample_rate = record_audio()

    # Convert audio to 16-bit PCM
    audio = np.clip(audio, -1.0, 1.0)
    audio = (audio * 32767).astype(np.int16)

    # Build fixed-vocabulary grammar
    phrases = [phrase for group in COMMANDS.values() for phrase in group]

    for number in OPTIONS:
        phrases.extend([
            number,
            "option " + number,
            "run option " + number,
            "select option " + number,
            "number " + number
        ])

    grammar = json.dumps(phrases + ["[unk]"])

    recognizer = KaldiRecognizer(model, sample_rate, grammar)
    recognizer.AcceptWaveform(audio.tobytes())

    result = json.loads(recognizer.FinalResult())
    text = result.get("text", "")

    print("Recognized:", text)

    return parse_command(text)


def main():
    """Test speech recognition."""

    if not MODEL_PATH.is_dir():
        print("Error: Vosk model not found.")
        return

    print("Loading speech recognition model...")
    model = Model(str(MODEL_PATH))

    command = recognize_command(model)

    if command:
        print("Selected Command:", command.upper())
    else:
        print("Command not recognized.")


if __name__ == "__main__":
    main()
