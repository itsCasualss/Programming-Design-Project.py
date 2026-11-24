"""Install start-on-login, application menu, and desktop shortcuts."""
import os
from pathlib import Path
import subprocess


def quote_exec(path):
    value = str(path).replace('%', '%%')
    for character in ('\\', '"', '`', '$'):
        value = value.replace(character, '\\' + character)
    return '"' + value.replace('\\', '\\\\') + '"'


def main():
    project = Path(__file__).resolve().parent
    launcher = project / 'launch_smartjeong.sh'
    if not launcher.is_file() or not (project / '.venv/bin/python').is_file():
        raise SystemExit('Install the launcher in the SmartJeong project with its existing .venv.')
    launcher.chmod(launcher.stat().st_mode | 0o100)

    home = Path.home()
    config = Path(os.environ.get('XDG_CONFIG_HOME') or home / '.config')
    data = Path(os.environ.get('XDG_DATA_HOME') or home / '.local/share')
    entry = (
        '[Desktop Entry]\n'
        'Type=Application\n'
        'Name=SmartJeong\n'
        f'Exec={quote_exec(launcher)}\n'
        'Icon=audio-input-microphone\n'
        'Terminal=false\n'
        'Categories=Utility;\n'
    )
    for directory in (config / 'autostart', data / 'applications'):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'smartjeong.desktop').write_text(entry)

    desktop = home / 'Desktop'
    try:
        output = subprocess.check_output(['xdg-user-dir', 'DESKTOP'], text=True).strip()
        if output:
            desktop = Path(output)
    except (OSError, subprocess.CalledProcessError):
        pass
    if desktop != home and desktop.is_dir():
        shortcut = desktop / 'SmartJeong.desktop'
        shortcut.write_text(entry)
        shortcut.chmod(0o755)
    print('SmartJeong starts at desktop login and is available from the application menu.')


if __name__ == '__main__':
    main()
