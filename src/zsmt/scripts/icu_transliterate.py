import icu

from argparse import ArgumentParser
from pathlib import Path
parser = ArgumentParser()
parser.add_argument('src_path')
parser.add_argument('out_path')

def transliterate(srcs, out_path=None, translit_str=None):
    translit_str = translit_str or 'Any-Latin; Latin-ASCII'
    tl = icu.Transliterator.createInstance(translit_str)
    translits = []
    if isinstance(srcs, str) or isinstance(srcs, Path):
        with open(srcs, "r") as r:
            srcs = [x.strip() for x in r.readlines()]
    if out_path:
        w = open(out_path, "w")
    for i, line in enumerate(srcs):
        transliteration = tl.transliterate(line)
        translits.append(transliteration)
        if out_path:
            w.write(transliteration)
            w.write("\n")
        if i % 10000 == 0:
            print(f'processed {i+1} lines', end="\r")
    if out_path:
        w.close()
    print(f"Finished transliterating {i+1} lines")
    return translits

if __name__ == '__main__':
    args = parser.parse_args()
    transliterate(args.src_path, args.out_path)
