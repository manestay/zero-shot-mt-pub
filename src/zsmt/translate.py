import datetime
from optparse import OptionParser

import torch
import torch.utils.data as data_utils
from torch.cuda.amp import autocast
from transformers import XLMRobertaTokenizer

from zsmt import dataset
from zsmt.seq2seq import Seq2Seq
from zsmt.seq_gen import BeamDecoder, get_outputs_until_eos

from zsmt.utils import get_token_id


def get_lm_option_parser():
    parser = OptionParser()
    parser.add_option("--input", dest="input_path", metavar="FILE", default=None)
    parser.add_option("--input2", dest="second_input_path", metavar="FILE", default=None)
    parser.add_option("--src", dest="src_lang", type="str", default=None)
    parser.add_option("--target", dest="target_lang", type="str", default=None)
    parser.add_option("--output", dest="output_path", metavar="FILE", default=None)
    parser.add_option("--batch", dest="batch", help="Batch size", type="int", default=4000)
    parser.add_option("--tok", dest="tokenizer_path", help="Path to the tokenizer folder", metavar="FILE", default=None)
    parser.add_option("--cache_size", dest="cache_size", help="Number of blocks in cache", type="int", default=300)
    parser.add_option("--model", dest="model_path", metavar="FILE", default=None)
    parser.add_option("--verbose", action="store_true", dest="verbose", help="Include input!", default=False)
    parser.add_option("--beam", dest="beam_width", type="int", default=4)
    parser.add_option("--max_len_a", dest="max_len_a", help="a for beam search (a*l+b)", type="float", default=1.3)
    parser.add_option("--max_len_b", dest="max_len_b", help="b for beam search (a*l+b)", type="int", default=5)
    parser.add_option("--len-penalty", dest="len_penalty_ratio", help="Length penalty", type="float", default=0.8)
    parser.add_option("--capacity", dest="total_capacity", help="Batch capacity", type="int", default=600)
    parser.add_option("--shallow", action="store_true", dest="shallow", default=False)
    parser.add_option("--lang", dest="lang_lines_path", default='',
            help="path to file with language family IDs for each input example")
    return parser


def translate_batch(batch, generator, text_processor, verbose=False):
    src_inputs = batch["src_texts"].squeeze(0)
    src_mask = batch["src_pad_mask"].squeeze(0)
    srct_inputs = batch["srct_texts"].squeeze(0)
    srct_mask = batch["srct_pad_mask"].squeeze(0)
    tgt_inputs = batch["dst_texts"].squeeze(0)
    src_pad_idx = batch["src_pad_idx"].squeeze(0)
    src_text = None
    if verbose:
        src_ids = get_outputs_until_eos(generator.seq2seq_model.src_eos_id(), src_inputs, remove_first_token=True)
        src_text = list(map(lambda src: generator.seq2seq_model.decode_src(src), src_ids))
    with autocast():
        outputs = generator(src_inputs=src_inputs, src_sizes=src_pad_idx,
                            srct_inputs=srct_inputs, srct_mask=srct_mask,
                            first_tokens=tgt_inputs[:, 0],
                            src_mask=src_mask,
                            pad_idx=text_processor.pad_token_id())
    mt_output = list(map(lambda x: text_processor.tokenizer.decode(x[1:].numpy()), outputs))
    return mt_output, src_text


def build_data_loader(options, text_processor):
    if not options.shallow:
        tokenizer_class, weights = XLMRobertaTokenizer, 'xlm-roberta-base'
        input_tokenizer = tokenizer_class.from_pretrained(weights)
    else:
        input_tokenizer = text_processor

    langs = {}
    if options.lang_lines_path:
        print(datetime.datetime.now(), 'Reading language lines!')
        with open(options.lang_lines_path, 'r') as l_fp:
            lang_lines = list(map(lambda x: x.strip(), l_fp))
        lang2id = {}
        src_bos_ids = [get_token_id(x, text_processor, lang2id) for x in lang_lines]
    else:
        print('Not using languages dict')
        bos_id = text_processor.bos_token_id()
        # count number of lines (could be more efficient?)
        with open(options.input_path, "r") as s_fp:
            num_lines = sum(1 for _ in s_fp)
        src_bos_ids = [bos_id] * num_lines


    print(datetime.datetime.now(), "Binarizing test data")
    fixed_output = [text_processor.token_id(text_processor.bos)]
    examples = []
    if options.second_input_path is not None:
        with open(options.input_path, "r") as s_fp, open(options.second_input_path, "r") as s2_fp:
            for i, (src_line, srct_line, bos_id) in enumerate(zip(s_fp, s2_fp, src_bos_ids)):
                if len(src_line.strip()) == 0: continue
                if not options.shallow:
                    src_tok_line = input_tokenizer.encode(src_line.strip())
                else:
                    src_tok_line = text_processor._tokenize(src_line.strip())
                    src_tok_line = [bos_id] + src_tok_line.ids + [text_processor.sep_token_id()]

                srct_tok_line = text_processor._tokenize(srct_line.strip())
                srct_tok_line = [bos_id] + srct_tok_line.ids + [text_processor.sep_token_id()]

                examples.append((src_tok_line, fixed_output, srct_tok_line))
                if i % 10000 == 0:
                    print(i, end="\r")
    else:
        with open(options.input_path, "r") as s_fp:
            for i, (src_line, bos_id) in enumerate(zip(s_fp, src_bos_ids)):
                if len(src_line.strip()) == 0: continue
                if not options.shallow:
                    src_tok_line = input_tokenizer.encode(src_line.strip())
                else:
                    src_tok_line = text_processor._tokenize(src_line.strip())
                    src_tok_line = [bos_id] + src_tok_line.ids + [text_processor.sep_token_id()]

                examples.append((src_tok_line, fixed_output, src_tok_line))
                if i % 10000 == 0:
                    print(i, end="\r")
    print("\n", datetime.datetime.now(), f"Loaded {len(examples)} examples")
    test_data = dataset.MTDataset(examples=examples, max_batch_capacity=options.total_capacity, max_batch=options.batch,
                                  dst_pad_idx=text_processor.pad_token_id(),
                                  src_pad_idx=text_processor.pad_token_id() if options.shallow else input_tokenizer.pad_token_id,
                                  max_seq_len=10000)
    pin_memory = torch.cuda.is_available()
    examples = None  # Make sure it gets collected
    return data_utils.DataLoader(test_data, batch_size=1, shuffle=False, pin_memory=pin_memory)


def build_model(options):
    model = Seq2Seq.load(Seq2Seq, options.model_path, tok_dir=options.tokenizer_path)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    model.eval()
    generator = BeamDecoder(model, beam_width=options.beam_width, max_len_a=options.max_len_a,
                            max_len_b=options.max_len_b, len_penalty_ratio=options.len_penalty_ratio)
    generator.eval()
    return generator, model.text_processor


def translate(options):
    generator, text_processor = build_model(options)
    print('building dataloader...')
    test_loader = build_data_loader(options, text_processor)
    sen_count = 0
    predictions = []
    with open(options.output_path, "w") as writer:
        with torch.no_grad():
            for batch in test_loader:
                try:
                    mt_output, src_text = translate_batch(batch, generator, text_processor, options.verbose)
                    sen_count += len(mt_output)
                    print(datetime.datetime.now(), "Translated", sen_count, "sentences", end="\r")
                    predictions.extend(mt_output)
                    if not options.verbose:
                        writer.write("\n".join(mt_output))
                    else:
                        writer.write("\n".join([y + " ||| " + x for x, y in zip(mt_output, src_text)]))
                    writer.write("\n")
                except RuntimeError as err:
                    print("\n", repr(err))

    print(datetime.datetime.now(), "Translated", sen_count, "sentences")
    print(datetime.datetime.now(), "Done!")
    return predictions

if __name__ == "__main__":
    parser = get_lm_option_parser()
    (options, args) = parser.parse_args()
    translate(options)
