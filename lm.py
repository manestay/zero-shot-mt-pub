import os
import pickle
import random
from typing import List

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AlbertModel, AlbertConfig
from transformers.modeling_albert import AlbertMLMHead

import lm_config
from textprocessor import TextProcessor


class LM(nn.Module):
    def __init__(self, text_processor: TextProcessor, config: AlbertConfig = None, encoder: AlbertModel = None,
                 size: int = 1):
        """
        :param size: config size: 1 big, 2 medium, 3 small.
        """
        super(LM, self).__init__()
        self.text_processor: TextProcessor = text_processor

        if config is not None:
            self.config = config
        else:
            if size == 3:
                self.config = lm_config._base_config(vocab_size=text_processor.tokenizer.get_vocab_size(),
                                                     pad_token_id=text_processor.pad_token_id(),
                                                     bos_token_id=text_processor.bos_token_id(),
                                                     eos_token_id=text_processor.sep_token_id())
            elif size == 2:
                self.config = lm_config._medium_config(vocab_size=text_processor.tokenizer.get_vocab_size(),
                                                       pad_token_id=text_processor.pad_token_id(),
                                                       bos_token_id=text_processor.bos_token_id(),
                                                       eos_token_id=text_processor.sep_token_id())
            elif size == 1:
                self.config = lm_config._small_config(vocab_size=text_processor.tokenizer.get_vocab_size(),
                                                      pad_token_id=text_processor.pad_token_id(),
                                                      bos_token_id=text_processor.bos_token_id(),
                                                      eos_token_id=text_processor.sep_token_id())
            elif size == 4:
                self.config = lm_config._toy_config(vocab_size=text_processor.tokenizer.get_vocab_size(),
                                                    pad_token_id=text_processor.pad_token_id(),
                                                    bos_token_id=text_processor.bos_token_id(),
                                                    eos_token_id=text_processor.sep_token_id())

            self.config["type_vocab_size"] = len(text_processor.languages)
            self.config = AlbertConfig(**self.config)

        self.masked_lm = AlbertMLMHead(self.config)
        if encoder is None:
            self.encoder: AlbertModel = AlbertModel(self.config)
            self.encoder.init_weights()
        else:
            self.encoder = encoder
        self.encoder._tie_or_clone_weights(self.masked_lm.decoder, self.encoder.embeddings.word_embeddings)

    def forward(self, device, mask: torch.Tensor, texts: torch.Tensor, pads: torch.Tensor, langs: List = None):
        """
        :param data: A minibatch as dictionary that has transformed image and tokenized text as long tensors.
        :return:
        """
        langs_tensor = langs.squeeze().unsqueeze(1).expand(-1, texts.size(1))

        texts = texts.to(device)
        pads = pads.to(device)
        langs_tensor = langs_tensor.to(device)
        text_hidden, text_cls_head = self.encoder(texts, attention_mask=pads, token_type_ids=langs_tensor)
        output_predictions = F.log_softmax(self.masked_lm(text_hidden[mask]), dim=1)
        return output_predictions

    @staticmethod
    def mask_text(mask_prob, pads, texts, text_processor: TextProcessor, mask_eos: bool = True):
        assert 0 < mask_prob < 1
        mask = torch.empty(texts.size()).uniform_(0, 1) < mask_prob
        mask[~pads] = False  # We should not mask pads.
        if not mask_eos:
            eos_idx = texts == text_processor.sep_token_id()
            mask[eos_idx] = False  # We should not mask end-of-sentence (usually in case of BART training).

        masked_ids = texts[mask]
        replacements = masked_ids.clone()
        for i in range(len(replacements)):
            r = random.random()
            if r < 0.8:
                replacements[i] = text_processor.mask_token_id()
            elif r < 0.9:
                # Replace with another random word.
                random_index = random.randint(len(text_processor.special_tokens), text_processor.vocab_size() - 1)
                replacements[i] = random_index
            else:
                # keep the word
                pass
        texts[mask] = replacements
        return mask, masked_ids, texts

    @staticmethod
    def unmask_text(mask, masked_ids, texts):
        # Return back the original masked elements!
        texts[mask] = masked_ids

    def save(self, out_dir: str):
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        with open(os.path.join(out_dir, "config"), "wb") as fp:
            pickle.dump(self.config, fp)

        torch.save(self.state_dict(), os.path.join(out_dir, "model.state_dict"))
        self.text_processor.save(directory=out_dir)

    @staticmethod
    def load(out_dir: str):
        text_processor = TextProcessor(tok_model_path=out_dir)
        with open(os.path.join(out_dir, "config"), "rb") as fp:
            config = pickle.load(fp)
            if isinstance(config, dict):
                # For older configs
                config = AlbertConfig(**config)
            lm = LM(text_processor=text_processor, config=config)
            lm.load_state_dict(torch.load(os.path.join(out_dir, "model.state_dict")))
            return lm
