import datetime
import marshal
from optparse import OptionParser

from transformers import XLMRobertaTokenizer

from textprocessor import TextProcessor


def write(text_processor: TextProcessor, output_file: str, src_txt_file: str, src_lang: int,
          dst_txt_file: str = None, dst_lang: int = None, min_len: int = 1, max_len: int = 175, shallow:bool=False):
    if not shallow:
        tokenizer_class, weights = XLMRobertaTokenizer, 'xlm-roberta-base'
        tokenizer = tokenizer_class.from_pretrained(weights)
    else:
        tokenizer = text_processor

    examples = {}
    line_num = 0
    src_lang_str = text_processor.languages[text_processor.id2token(src_lang)]
    lens = {}
    if dst_txt_file is not None:
        dst_lang_str = text_processor.languages[text_processor.id2token(dst_lang)]
        with open(src_txt_file, "r") as s_fp, open(dst_txt_file, "r") as d_fp:
            for src_line, dst_line in zip(s_fp, d_fp):
                if len(src_line.strip()) == 0 or len(dst_line.strip()) == 0: continue
                if not shallow:
                    src_tok_line = tokenizer.encode(src_line.strip())
                else:
                    src_tok_line = text_processor.tokenize_one_sentence_with_langid(src_line.strip(), src_lang)

                dst_tok_line = text_processor.tokenize_one_sentence_with_langid(dst_line.strip(), dst_lang)

                if min_len <= len(src_tok_line) <= max_len and min_len <= len(dst_tok_line) <= max_len:
                    examples[line_num] = (src_tok_line, dst_tok_line, dst_lang_str)
                    lens[line_num] = len(dst_tok_line)
                    line_num += 1

                if line_num % 1000 == 0:
                    print(line_num, end="\r")

        print("\nSorting")
        sorted_lens = sorted(lens.items(), key=lambda item: item[1])
        sorted_examples = []
        print("Sorted examples")
        for len_item in sorted_lens:
            line_num = len(sorted_examples)
            sorted_examples.append(examples[len_item[0]])

        print("Dumping")
        with open(output_file, "wb") as fw:
            marshal.dump(sorted_examples, fw)

    else:
        part_num = 0
        # Used for MASS training where we only have source sentences.
        with open(src_txt_file, "r") as s_fp:
            for src_line in s_fp:
                if len(src_line.strip()) == 0: continue
                src_tok_line = text_processor.tokenize_one_sentence_with_langid(src_line.strip(), src_lang)
                if min_len <= len(src_tok_line) <= max_len:
                    examples[line_num] = (src_tok_line, src_lang_str)
                    lens[line_num] = len(src_tok_line)
                    line_num += 1
                    if line_num % 1000 == 0:
                        print(line_num, "\r", end="")

                if len(examples) >= 6000000:
                    print(datetime.datetime.now(), "Sorting and writing", part_num)
                    sorted_lens = sorted(lens.items(), key=lambda item: item[1])
                    sorted_examples = list(map(lambda len_item: examples[len_item[0]], sorted_lens))
                    with open(output_file + "." + str(part_num), "wb") as fw:
                        marshal.dump(sorted_examples, fw)
                    examples = {}
                    lens = {}
                    part_num += 1

        if len(examples) > 0:
            print(datetime.datetime.now(), "Sorting and writing", part_num)
            sorted_lens = sorted(lens.items(), key=lambda item: item[1])
            sorted_examples = list(map(lambda len_item: examples[len_item[0]], sorted_lens))
            with open(output_file + "." + str(part_num), "wb") as fw:
                marshal.dump(sorted_examples, fw)


def get_options():
    global options
    parser = OptionParser()
    parser.add_option("--src", dest="src_data_path", help="Path to the source txt file", metavar="FILE", default=None)
    parser.add_option("--dst", dest="dst_data_path", help="Path to the target txt file", metavar="FILE", default=None)
    parser.add_option("--output", dest="output_path", help="Output marshal file ", metavar="FILE", default=None)
    parser.add_option("--tok", dest="tokenizer_path", help="Path to the tokenizer folder", metavar="FILE", default=None)
    parser.add_option("--max_seq_len", dest="max_seq_len", help="Max sequence length", type="int", default=175)
    parser.add_option("--min_seq_len", dest="min_seq_len", help="Max sequence length", type="int", default=1)
    parser.add_option("--src-lang", dest="src_lang", type="str", default=None)
    parser.add_option("--dst-lang", dest="dst_lang", type="str", default=None)
    parser.add_option("--shallow", action="store_true", dest="shallow_encoder",
                      help="Use shallow encoder instead of XLM", default=False)
    (options, args) = parser.parse_args()
    return options


if __name__ == "__main__":
    options = get_options()
    tokenizer = TextProcessor(options.tokenizer_path)

    print(datetime.datetime.now(), "Writing batches")
    src_lang = tokenizer.token_id("<" + options.src_lang + ">")
    dst_lang = tokenizer.token_id("<" + options.dst_lang + ">") if options.dst_lang is not None else None
    write(text_processor=tokenizer, output_file=options.output_path, src_txt_file=options.src_data_path,
          dst_txt_file=options.dst_data_path, src_lang=src_lang, dst_lang=dst_lang, shallow=options.shallow_encoder)
    print(datetime.datetime.now(), "Finished")
