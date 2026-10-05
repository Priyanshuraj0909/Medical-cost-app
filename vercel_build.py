"""Bundle LightGBM's OpenMP dependency for Vercel's Linux runtime."""
from pathlib import Path
import shutil
import subprocess


def main():
    candidates = [Path('/usr/lib64/libgomp.so.1'), Path('/usr/lib/x86_64-linux-gnu/libgomp.so.1')]
    try:
        candidates.append(Path(subprocess.check_output(['gcc', '-print-file-name=libgomp.so.1'], text=True).strip()))
    except (OSError, subprocess.CalledProcessError):
        pass
    for candidate in candidates:
        if candidate.is_file():
            target = Path('native/libgomp.so.1')
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(candidate.resolve(), target)
            print(f'Bundled OpenMP runtime from {candidate}')
            return
    raise RuntimeError('OpenMP library not found on the build machine')


if __name__ == '__main__':
    main()
