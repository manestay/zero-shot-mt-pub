'''
Generate lang_fam.txt from raw WikiMatrix data.
`--parts-dir` should be a dir containing the parallel texts generated from following the
WikiMatrix README (https://github.com/facebookresearch/LASER/tree/main/tasks/WikiMatrix) up to
`extract.py`
'''

import argparse
from pathlib import Path

from zsmt.lang_info import get_langs_d

parser = argparse.ArgumentParser()
parser.add_argument('--parts-dir', '-i', type=Path, default='/home/bli2/data/wikimatrix-parts')
parser.add_argument('--out-path', '-o', type=Path, default='/home/bli2/data/WikiMatrix/WikiMatrix.train.lang_fam.txt')
parser.add_argument('--langs-path', '-l', type=Path, default='./lang_info.json')

if __name__ == "__main__":
    args = parser.parse_args()
    langs_d = get_langs_d(args.langs_path)
    with args.out_path.open('w') as f:
        for fname in sorted(args.parts_dir.glob('*.txt.*')):
            print(f'processing {fname}')
            if fname.suffix == '.en':
                continue
            lang = fname.suffix[1:]
            lang_fam = langs_d[lang]
            print(lang_fam)
            with fname.open('r') as f_in:
                for line in f_in:
                    f.write(lang_fam + '\n')
