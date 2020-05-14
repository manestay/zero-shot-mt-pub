import json
import os
import pickle
from collections import defaultdict
from optparse import OptionParser

import torch

from textprocessor import TextProcessor


def write(text_processor: TextProcessor, output_file: str, json_dir: str, files_to_use: str = None):
    relevant_files = None
    if files_to_use is not None:
        relevant_files = {f + ".json" for f in files_to_use.strip().split(",")}

    num_captions, num_docs, max_doc_size = 0, 0, 0
    unique_docs = {}
    image_info_dict = defaultdict(list)

    for file in os.listdir(json_dir):
        if not file.endswith(".json"):
            continue
        if relevant_files is not None and file not in relevant_files:
            continue

        print(file)

        with open(os.path.join(json_dir, file), "rb") as fp:
            doc_dicts = json.load(fp)
            max_caption_len = 0
            for doc in doc_dicts:
                content = doc["content"]
                lang = doc["lang"]
                tok_lines = text_processor.tokenize_lines(content.strip())

                doc_id = len(unique_docs)
                unique_docs[doc_id] = [torch.LongTensor(t) for t in tok_lines]

                max_doc_size = max(max_doc_size, len(unique_docs[doc_id]))
                num_captions += len(doc["images"])
                for image in doc["images"]:
                    path = image["img_path"]
                    caption = text_processor.tokenize_one_line(image["caption"], ignore_middle_eos=True)
                    image_info_dict[path].append((caption, lang, doc_id))
                    max_caption_len = max(len(caption), max_caption_len)

            print(len(doc_dicts), max_caption_len, max_doc_size)
    print("%d images, %d docs, %d captions, max doc vec %d" % (
        len(image_info_dict), len(unique_docs), num_captions, max_doc_size))
    with open(output_file, "wb") as fp:
        pickle.dump((image_info_dict, unique_docs), fp)


def get_options():
    global options
    parser = OptionParser()
    parser.add_option("--data", dest="data_path", help="Path to the data folder", metavar="FILE", default=None)
    parser.add_option("--files", dest="files_to_use", help="Which files to use", type="str", default=None)
    parser.add_option("--output", dest="output_file", help="Output pickle file.", metavar="FILE", default=None)
    parser.add_option("--tok", dest="tokenizer_path", help="Path to the tokenizer folder", metavar="FILE", default=None)
    (options, args) = parser.parse_args()
    return options


if __name__ == "__main__":
    options = get_options()
    tokenizer = TextProcessor(options.tokenizer_path)

    print("writing batches")
    write(text_processor=tokenizer,
          output_file=options.output_file,
          json_dir=options.data_path,
          files_to_use=options.files_to_use)
    print("finished")
