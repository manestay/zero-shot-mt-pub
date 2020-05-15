import json
import os
import pickle
from collections import defaultdict
from optparse import OptionParser

import torch

from textprocessor import TextProcessor


def write(text_processor: TextProcessor, output_file: str, json_dir: str, files_to_use: str = None,
          max_sen_per_doc: int = 32):
    relevant_files = None
    if files_to_use is not None:
        relevant_files = {f + ".json" for f in files_to_use.strip().split(",")}

    num_captions, num_docs, max_doc_size = 0, 0, 0
    unique_docs = {}
    unique_images = {}
    image_path_dict = {}
    image_info_dict = defaultdict(list)
    num_docs = 0

    for file in os.listdir(json_dir):
        if not file.endswith(".json"):
            continue
        if relevant_files is not None and file not in relevant_files:
            continue

        print(file)

        with open(os.path.join(json_dir, file), "rb") as fp:
            doc_dicts = json.load(fp)
            max_caption_len = 0
            num_docs += len(doc_dicts)
            print(len(doc_dicts), num_docs)
            for d_num, doc in enumerate(doc_dicts):
                content = doc["content"]
                lang = doc["lang"]
                tok_lines = text_processor.tokenize_lines(content.strip(), blind_split=True, split_len=128)
                doc_lines = torch.LongTensor(tok_lines)
                doc_segments = torch.split(doc_lines, max_sen_per_doc)

                for doc_segment in doc_segments:
                    doc_id = len(unique_docs)
                    unique_docs[doc_id] = doc_segment

                    max_doc_size = max(max_doc_size, len(unique_docs[doc_id]))
                    num_captions += len(doc["images"])
                    for image in doc["images"]:
                        path = image["img_path"]
                        if path not in image_path_dict:
                            image_id = len(unique_images)
                            unique_images[image_id] = path
                            image_path_dict[path] = image_id
                        else:
                            image_id = image_path_dict[path]
                            unique_images[image_id] = path

                        caption = text_processor.tokenize_one_line(image["caption"], ignore_middle_eos=True)
                        image_info_dict[image_id].append((caption, lang, doc_id))
                        max_caption_len = max(len(caption), max_caption_len)

                if (d_num + 1) % 10000 == 0:
                    print("***", d_num + 1, len(image_info_dict))

            print(len(doc_dicts), max_caption_len, max_doc_size, "->", num_docs, len(image_info_dict))

    num_instances = 0
    for image, caption_infos in image_info_dict.items():
        captions = [c[0] for c in caption_infos]
        langs = [c[1] for c in caption_infos]
        docs = [c[2] for c in caption_infos]

        for d_i, doc in enumerate(docs):
            for c_i, caption in enumerate(captions):
                if c_i != d_i and langs[c_i] == langs[d_i]:
                    # Skip different docs with same language.
                    continue
                num_instances += 1

    print("%d images, %d docs, %d captions, max doc vec %d, training instances %d" % (
        len(image_info_dict), len(unique_docs), num_captions, max_doc_size, num_instances))

    with open(output_file, "wb") as fp:
        pickle.dump((image_info_dict, unique_images, unique_docs), fp)


def get_options():
    global options
    parser = OptionParser()
    parser.add_option("--data", dest="data_path", help="Path to the data folder", metavar="FILE", default=None)
    parser.add_option("--files", dest="files_to_use", help="Which files to use", type="str", default=None)
    parser.add_option("--output", dest="output_file", help="Output pickle file.", metavar="FILE", default=None)
    parser.add_option("--tok", dest="tokenizer_path", help="Path to the tokenizer folder", metavar="FILE", default=None)
    parser.add_option("--max_sen", dest="max_sen",
                      help="Maximum number of sentences in one document. If more, will split", type=int, default=64)
    (options, args) = parser.parse_args()
    return options


if __name__ == "__main__":
    options = get_options()
    tokenizer = TextProcessor(options.tokenizer_path)

    print("writing batches")
    write(text_processor=tokenizer,
          output_file=options.output_file,
          json_dir=options.data_path,
          files_to_use=options.files_to_use,
          max_sen_per_doc=options.max_sen)
    print("finished")
