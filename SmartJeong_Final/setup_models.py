"""Explicit model setup; no model downloads occur during an interaction."""
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / 'models'
VOSK_NAME = 'vosk-model-small-en-us-0.15'
VOSK_URL = 'https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip'


def download(url, target):
    import requests
    deadline, size = time.monotonic() + 300, 0
    with requests.get(url, stream=True, timeout=(10, 20)) as response:
        response.raise_for_status()
        with target.open('wb') as output:
            for block in response.iter_content(65536):
                size += len(block)
                if size > 150_000_000 or time.monotonic() > deadline:
                    raise RuntimeError('Model transfer limit exceeded')
                output.write(block)


def download_vosk():
    MODELS_DIR.mkdir(exist_ok=True)
    target = MODELS_DIR / VOSK_NAME
    if (target / 'am/final.mdl').is_file() and (target / 'conf/model.conf').is_file():
        return
    if target.exists():
        raise RuntimeError('Incomplete Vosk directory; rename it before retrying setup')
    with tempfile.TemporaryDirectory(dir=MODELS_DIR) as temporary:
        temporary = Path(temporary)
        archive_path = temporary / 'vosk.zip'
        download(VOSK_URL, archive_path)
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                path = (temporary / member.filename).resolve()
                if not path.is_relative_to(temporary.resolve()):
                    raise RuntimeError('Unsafe archive path')
            if sum(item.file_size for item in archive.infolist()) > 250_000_000:
                raise RuntimeError('Archive too large')
            archive.extractall(temporary)
        extracted = temporary / VOSK_NAME
        if not (extracted / 'am/final.mdl').is_file():
            raise RuntimeError('Incomplete model archive')
        shutil.move(str(extracted), str(target))


def download_openwakeword():
    # Resolve official release URLs from the pinned package; download only ONNX assets.
    import openwakeword
    folder = Path(openwakeword.__file__).parent / 'resources/models'
    folder.mkdir(parents=True, exist_ok=True)
    assets = list(openwakeword.FEATURE_MODELS.values()) + [openwakeword.MODELS['hey_jarvis']]
    for asset in assets:
        url = asset['download_url'].replace('.tflite', '.onnx')
        target = folder / url.rsplit('/', 1)[-1]
        if target.is_file(): continue
        temporary = target.with_suffix('.part')
        try:
            download(url, temporary)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    from openwakeword.model import Model
    import numpy as np
    model = Model(wakeword_models=['hey_jarvis'], inference_framework='onnx')
    model.predict(np.zeros(1280, dtype=np.int16))
    model.reset()
    print('ONNX model loads and accepts a 16 kHz PCM frame. Acoustic validation still required.')


def main():
    download_vosk()
    download_openwakeword()
    from vosk import Model
    Model(str(MODELS_DIR / VOSK_NAME))
    print('Both model loaders passed.')


if __name__ == '__main__': main()
