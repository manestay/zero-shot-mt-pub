'''
Download subset of WikiMatrix data based on allowed languages for LWLL.
'''
import json

from pathlib import Path
from subprocess import call, Popen

import pandas as pd

allowed_codes = \
    set(["afr", "aka", "asm", "aze", "bam", "bre", "cat", "ces", "dan", "deu", "est", "eus",
    "fao", "fin", "fra", "glg", "hau", "heb", "hye", "isl", "ita", "jav", "kan", "kat", "kor", "lao",
    "lat", "ltz", "lug", "mkd", "mlg", "mlt", "msa", "nde", "nor", "nya", "oci", "ori", "orm", "pan",
    "pus", "rus", "srp", "tam", "tel", "tgl", "tir", "tsn", "tur", "ukr", "urd", "vie", "wol", "xho",
    "zho"])

def get_allowed_codes(df, langs):
    to_download = []
    codes_found = set()
    for fname in df['tsv']:
        _, pair, _ = fname.split('.')
        l1, l2 = pair.split('-')
        if l1 == 'en':
            en, oth = l1, l2
        elif l2 == 'en':
            oth, en = l1, l2
        else:
            continue
        lang_code = langs.get(oth, {}).get('ISO639P3code', '')

        if oth == 'zh':
            lang_code = 'zho'

        if not lang_code:
            pass
            # print(f'code {oth} not found')
        elif lang_code not in allowed_codes:
            pass
            # print(f'code {oth} found, but {lang_code} not allowed!')
        else:
            to_download.append(oth)
            codes_found.add(lang_code)
            print(langs[oth]['Name'])
            # print(f'code {oth}, {lang_code} added')
    return to_download, codes_found

if __name__ == "__main__":
    bitexts = Path('./list_of_bitexts.txt')
    lang_path = Path('./lang_info.json')
    with lang_path.open('r') as f:
        langs = json.load(f)
    df = pd.read_csv(bitexts, sep='\t', names=['tsv', 'num_lines'])

    to_download, codes_found = get_allowed_codes(df, langs)
    # print('to_download codes:', to_download)
    # print('not found', allowed_codes - codes_found)

    # for i, wiki_code in enumerate(to_download, 1):
    #     pair = '-'.join(sorted(['en', wiki_code]))
    #     cmd = f'wget https://dl.fbaipublicfiles.com/laser/WikiMatrix/v1/WikiMatrix.{pair}.tsv.gz'
    #     print(f'running {cmd} ({i}/{len(to_download)})')
    #     Popen(cmd, shell=True)
