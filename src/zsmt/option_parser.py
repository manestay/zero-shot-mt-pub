from optparse import OptionParser


def get_mt_options_parser():
    parser = OptionParser()
    parser.add_option("--tok", dest="tokenizer_path", help="Path to the tokenizer folder", metavar="FILE", default=None)
    parser.add_option("--cache_size", dest="cache_size", help="Number of blocks in cache", type="int", default=300)
    parser.add_option("--model", dest="model_path", help="Directory path to save the best model", metavar="FILE",
                      default=None)
    parser.add_option("--pretrained", dest="pretrained_path", help="Directory of pretrained model", metavar="FILE",
                      default=None)
    parser.add_option("--epoch", dest="num_epochs", help="Number of training epochs", type="int", default=100)
    parser.add_option("--clip", dest="clip", help="For gradient clipping", type="int", default=1)
    parser.add_option("--batch", dest="batch", help="Batch size", type="int", default=6000)
    parser.add_option("--mask", dest="mask_prob", help="Random masking probability", type="float", default=0.15)
    parser.add_option("--lr", dest="learning_rate", help="Learning rate", type="float", default=0.0001)
    parser.add_option("--warmup", dest="warmup", help="Number of warmup steps", type="int", default=12500)
    parser.add_option("--step", dest="step", help="Number of training steps", type="int", default=125000)
    parser.add_option("--max_grad_norm", dest="max_grad_norm", help="Max grad norm", type="float", default=1.0)
    parser.add_option("--cont", action="store_true", dest="continue_train",
                      help="Continue training from pretrained model", default=False)
    parser.add_option("--dropout", dest="dropout", help="Dropout probability", type="float", default=0.1)
    parser.add_option("--embed", dest="embed_dim", help="Embedding dimension", type="int", default=768)
    parser.add_option("--intermediate", dest="intermediate_layer_dim", type="int", default=3072)
    parser.add_option("--local_rank", dest="local_rank", type=int, default=-1)
    parser.add_option("--capacity", dest="total_capacity", help="Batch capacity", type="int", default=600)
    parser.add_option("--dict", dest="dict_path", help="External lexical dictionary", metavar="FILE", default=None)
    parser.add_option("--beam", dest="beam_width", help="Beam width", type="int", default=5)
    parser.add_option("--bt-beam", dest="bt_beam_width", help="Beam width for back-translation loss", type="int",
                      default=1)
    parser.add_option("--max_len_a", dest="max_len_a", help="a for beam search (a*l+b)", type="float", default=1.3)
    parser.add_option("--max_len_b", dest="max_len_b", help="b for beam search (a*l+b)", type="int", default=5)
    parser.add_option("--len-penalty", dest="len_penalty_ratio", help="Length penalty", type="float", default=0.8)
    parser.add_option("--max_seq_len", dest="max_seq_len", help="Max sequence length", type="int", default=175)
    parser.add_option("--ldec", action="store_true", dest="lang_decoder", help="Lang-specific decoder", default=False)
    parser.add_option("--nll", action="store_true", dest="nll_loss", help="Use NLL loss instead of smoothed NLL loss",
                      default=False)
    parser.set_default("batch", 20000)
    parser.add_option("--dev", dest="mt_dev_path",
                      help="Path to the MT dev data pickle files (SHOULD NOT BE USED IN UNSUPERVISED SETTING)",
                      metavar="FILE", default=None)
    parser.add_option("--train", dest="mt_train_path",
                      help="Path to the MT train data pickle files (SHOULD NOT BE USED IN PURELY UNSUPERVISED SETTING)",
                      metavar="FILE", default=None)
    parser.set_default("mask_prob", 0.5)
    parser.add_option("--dec", dest="decoder_layer", help="# decoder layers", type="int", default=6)
    parser.add_option("--output", dest="output", help="Output file (for simiality)", metavar="FILE", default=None)
    parser.add_option("--save-opt", action="store_true", dest="save_opt", default=False)
    parser.add_option("--acc", dest="accum", help="Gradient accumulation", type="int", default=1)
    parser.add_option("--freeze", action="store_true", dest="freeze_encoder", default=False)
    parser.add_option("--shallow", action="store_true", dest="shallow_encoder",
                      help="Use shallow encoder instead of XLM", default=False)
    parser.add_option("--multi", action="store_true", dest="multi_stream",
                      help="Using multi-stream model (the batches should be built via multi-stream)", default=False)
    parser.add_option("--load-separate-train", action="store_true", dest="load_separate_train", default=False)
    parser.add_option("--eval-steps", dest="eval_steps", help='number of steps before running evaluation', type="int", default=5000)
    parser.add_option("--early-stop", dest="early_stop", help="Num of epochs before early stop", type="int", default=0)
    return parser
