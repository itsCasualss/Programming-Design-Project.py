"""Model/API smoke test with silence, not an acoustic recognition test."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from setup_models import MODELS_DIR, VOSK_NAME


def main():
    import numpy as np
    from openwakeword.model import Model as WakeModel
    from vosk import Model, KaldiRecognizer, SetLogLevel
    wake = WakeModel(wakeword_models=['hey_jarvis'], inference_framework='onnx')
    scores = {}
    for _ in range(20): scores = wake.predict(np.zeros(1280, dtype=np.int16))
    assert scores and all(np.isfinite(float(value)) for value in scores.values())
    wake.reset()
    SetLogLevel(-1)
    grammar = ['schedule', 'pills', 'weather', 'news', 'one', 'two', 'three', 'four', '[unk]']
    recognizer = KaldiRecognizer(Model(str(MODELS_DIR / VOSK_NAME)), 16000, json.dumps(grammar))
    recognizer.AcceptWaveform(bytes(16000 * 2))
    result = json.loads(recognizer.FinalResult())
    assert not result.get('text', '').strip(), result
    print('PASS: ONNX finite scores/reset and Vosk fixed grammar/silence. Real acoustics NOT tested.')


if __name__ == '__main__': main()
