"""Explicit one-time model download; robot startup never downloads files."""
from pathlib import Path
import urllib.request

BASE_URL = 'https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/'
FILES = {'deploy.prototxt': 40000, 'mobilenet_iter_73000.caffemodel': 23000000}


def main():
    destination = Path(__file__).resolve().parent / 'models'
    destination.mkdir(exist_ok=True)
    for name, minimum_size in FILES.items():
        target = destination / name
        if target.exists() and target.stat().st_size >= minimum_size:
            print(f'Already present: {target}')
            continue
        temporary = target.with_suffix(target.suffix + '.part')
        print(f'Downloading {name}...', flush=True)
        try:
            with urllib.request.urlopen(BASE_URL + name, timeout=60) as response, temporary.open('wb') as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
            if temporary.stat().st_size < minimum_size:
                raise RuntimeError(f'Incomplete model download: {name}')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    print('Person model ready.')


if __name__ == '__main__':
    main()
