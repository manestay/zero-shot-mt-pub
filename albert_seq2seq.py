from transformers.modeling_albert import *

from lm import LM
from textprocessor import TextProcessor


class AlbertSeq2Seq(nn.Module):
    def __init__(self, lm: LM):
        super(AlbertSeq2Seq, self).__init__()
        self.text_processor: TextProcessor = lm.text_processor
        self.config = lm.encoder.config
        self.encoder: AlbertModel = lm.encoder
        self.decoder: AlbertDecoderModel = AlbertDecoderModel(self.encoder)
        self.output_layer = lm.output_layer  # nn.Linear(self.config["hidden_size"], self.text_processor.vocab_size(), )

    def forward(self, device, src_inputs, tgt_inputs, src_mask, tgt_mask):
        "Take in and process masked src and target sequences."
        src_inputs = src_inputs.to(device)
        tgt_inputs = tgt_inputs.to(device)
        src_mask = src_mask.to(device)
        tgt_mask = tgt_mask.to(device)

        encoder_states = self.encoder(src_inputs, attention_mask=src_mask)
        return self.decoder(encoder_states[0], tgt_inputs, src_mask, tgt_mask)


class AlbertDecoderAttention(nn.Module):
    def __init__(self, albert_attention: AlbertAttention):
        super().__init__()
        self.albert_attention = albert_attention
        self.output_attentions = albert_attention.output_attentions  # config.output_attentions
        self.dropout = albert_attention.dropout
        self.num_attention_heads = albert_attention.num_attention_heads
        self.hidden_size = albert_attention.hidden_size
        self.attention_head_size = albert_attention.attention_head_size
        self.all_head_size = albert_attention.all_head_size

        self.query = albert_attention.query  # nn.Linear(config.hidden_size, self.all_head_size)
        self.key = albert_attention.key  # nn.Linear(config.hidden_size, self.all_head_size)
        self.value = albert_attention.value  # nn.Linear(config.hidden_size, self.all_head_size)

        self.dense = albert_attention.dense  # nn.Linear(config.hidden_size, config.hidden_size)
        self.LayerNorm = albert_attention.LayerNorm  # nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)
        self.pruned_heads = set()

    def prune_heads(self, heads):
        return self.albert_attention(heads)

    def transpose_for_scores(self, x):
        new_x_shape = x.size()[:-1] + (self.num_attention_heads, self.attention_head_size)
        x = x.view(*new_x_shape)
        return x.permute(0, 2, 1, 3)

    def forward(self, encoder_states, output_ids, src_attention_mask=None, tgt_attention_mask=None, head_mask=None):
        output_ids_q = self.query(output_ids)
        output_ids_k = self.key(output_ids)
        output_ids_v = self.value(output_ids)
        encoder_states_k = self.key(encoder_states)
        encoder_states_v = self.value(encoder_states)

        attention_output = self.attention(output_ids_q, output_ids_k, output_ids_v, tgt_attention_mask)
        attention_output = self.attention(attention_output[0], encoder_states_k, encoder_states_v)
        return attention_output

    def attention(self, q, k, v, src_attention_mask=None, tgt_attention_mask=None, head_mask=None):
        query_layer = self.transpose_for_scores(q)
        key_layer = self.transpose_for_scores(k)
        value_layer = self.transpose_for_scores(v)

        # Take the dot product between "query" and "key" to get the raw attention scores.
        attention_scores = torch.matmul(query_layer, key_layer.transpose(-1, -2))
        attention_scores = attention_scores / math.sqrt(self.attention_head_size)
        if src_attention_mask is not None:
            # Apply the attention mask is (precomputed for all layers in BertModel forward() function)
            attention_scores = attention_scores + src_attention_mask

        if tgt_attention_mask is not None:
            # Apply the attention mask is (precomputed for all layers in BertModel forward() function)
            attention_scores = attention_scores + tgt_attention_mask

        # Normalize the attention scores to probabilities.
        attention_probs = nn.Softmax(dim=-1)(attention_scores)

        # This is actually dropping out entire tokens to attend to, which might
        # seem a bit unusual, but is taken from the original Transformer paper.
        attention_probs = self.dropout(attention_probs)

        # Mask heads if we want to
        if head_mask is not None:
            attention_probs = attention_probs * head_mask

        context_layer = torch.matmul(attention_probs, value_layer)

        context_layer = context_layer.permute(0, 2, 1, 3).contiguous()

        # Should find a better way to do this
        w = (
            self.dense.weight.t()
                .view(self.num_attention_heads, self.attention_head_size, self.hidden_size)
                .to(context_layer.dtype)
        )
        b = self.dense.bias.to(context_layer.dtype)

        projected_context_layer = torch.einsum("bfnd,ndh->bfh", context_layer, w) + b
        projected_context_layer_dropout = self.dropout(projected_context_layer)
        layernormed_context_layer = self.LayerNorm(q + projected_context_layer_dropout)
        return (layernormed_context_layer, attention_probs) if self.output_attentions else (layernormed_context_layer,)


class AlbertDecoderLayer(nn.Module):
    def __init__(self, albert_layer: AlbertLayer):
        super().__init__()

        self.full_layer_layer_norm = albert_layer.full_layer_layer_norm  # nn.LayerNorm(self.config.hidden_size, eps=self.config.layer_norm_eps) #todo clone
        self.attention = AlbertDecoderAttention(albert_layer.attention)
        self.ffn = albert_layer.ffn  # nn.Linear(self.config.hidden_size, self.config.intermediate_size) #todo clone
        self.ffn_output = albert_layer.ffn_output  # nn.Linear(self.config.intermediate_size, self.config.hidden_size) #todo clone
        self.activation = albert_layer.activation  # ACT2FN[self.config.hidden_act]

    def forward(self, encoder_states, hidden_states, src_attention_mask=None, tgt_attention_mask=None, head_mask=None):
        attention_output = self.attention(encoder_states, hidden_states, src_attention_mask, tgt_attention_mask,
                                          head_mask)
        ffn_output = self.ffn(attention_output[0])
        ffn_output = self.activation(ffn_output)
        ffn_output = self.ffn_output(ffn_output)
        hidden_states = self.full_layer_layer_norm(ffn_output + attention_output[0])

        return (hidden_states,) + attention_output[1:]  # add attentions if we output them


class AlbertDecoderLayerGroup(nn.Module):
    def __init__(self, layer_groups: AlbertLayerGroup):
        super().__init__()

        self.output_attentions = layer_groups.output_attentions
        self.output_hidden_states = layer_groups.output_hidden_states
        self.albert_layers = nn.ModuleList([AlbertDecoderLayer(layer) for layer in layer_groups.albert_layers])

    def forward(self, encoder_states, hidden_states, src_attention_mask=None, tgt_attention_mask=None, head_mask=None):
        layer_hidden_states = ()
        layer_attentions = ()

        for layer_index, albert_layer in enumerate(self.albert_layers):
            layer_output = albert_layer(encoder_states, hidden_states, src_attention_mask, tgt_attention_mask,
                                        head_mask[layer_index])
            hidden_states = layer_output[0]

            if self.output_attentions:
                layer_attentions = layer_attentions + (layer_output[1],)

            if self.output_hidden_states:
                layer_hidden_states = layer_hidden_states + (hidden_states,)

        outputs = (hidden_states,)
        if self.output_hidden_states:
            outputs = outputs + (layer_hidden_states,)
        if self.output_attentions:
            outputs = outputs + (layer_attentions,)
        return outputs  # last-layer hidden state, (layer hidden states), (layer attentions)


class AlbertDecoderTransformer(nn.Module):
    def __init__(self, albert_transformer: AlbertTransformer):
        super().__init__()

        self.config = albert_transformer.config
        self.output_attentions = self.config.output_attentions
        self.output_hidden_states = self.config.output_hidden_states
        self.embedding_hidden_mapping_in = albert_transformer.embedding_hidden_mapping_in
        self.albert_layer_groups = nn.ModuleList(
            [AlbertDecoderLayerGroup(albert_transformer.albert_layer_groups[i]) for i in
             range(self.config.num_hidden_groups)])

    def forward(self, encoder_states, hidden_states, src_attention_mask=None, tgt_attention_mask=None, head_mask=None):
        hidden_states = self.embedding_hidden_mapping_in(hidden_states)

        all_attentions = ()

        all_hidden_states = None
        if self.output_hidden_states:
            all_hidden_states = (hidden_states,)

        for i in range(self.config.num_hidden_layers):
            # Number of layers in a hidden group
            layers_per_group = int(self.config.num_hidden_layers / self.config.num_hidden_groups)

            # Index of the hidden group
            group_idx = int(i / (self.config.num_hidden_layers / self.config.num_hidden_groups))

            layer_group_output = self.albert_layer_groups[group_idx](
                encoder_states,
                hidden_states,
                src_attention_mask,
                tgt_attention_mask,
                head_mask[group_idx * layers_per_group: (group_idx + 1) * layers_per_group],
            )
            hidden_states = layer_group_output[0]

            if self.output_attentions:
                all_attentions = all_attentions + layer_group_output[-1]

            if self.output_hidden_states:
                all_hidden_states = all_hidden_states + (hidden_states,)

        outputs = (hidden_states,)
        if self.output_hidden_states:
            outputs = outputs + (all_hidden_states,)
        if self.output_attentions:
            outputs = outputs + (all_attentions,)
        return outputs


class AlbertDecoderModel(AlbertPreTrainedModel):
    config_class = AlbertConfig
    base_model_prefix = "albert"

    def __init__(self, encoder_layer: AlbertModel):
        super().__init__(encoder_layer.config)
        self.encoder_layer = encoder_layer
        self.config = encoder_layer.config
        self.embeddings = encoder_layer.embeddings
        self.decoder = AlbertDecoderTransformer(encoder_layer.encoder)
        self.pooler = encoder_layer.pooler  # nn.Linear(self.config.hidden_size, self.config.hidden_size)
        self.pooler_activation = encoder_layer.pooler_activation  # nn.Tanh()

        self.init_weights()

    def get_input_embeddings(self):
        return self.embeddings.word_embeddings

    def set_input_embeddings(self, value):
        self.embeddings.word_embeddings = value

    def _resize_token_embeddings(self, new_num_tokens):
        self.encoder_layer._resize_token_embeddings(new_num_tokens)

    def _pzrune_heads(self, heads_to_prune):
        """ Prunes heads of the model.
            heads_to_prune: dict of {layer_num: list of heads to prune in this layer}
            ALBERT has a different architecture in that its layers are shared across groups, which then has inner groups.
            If an ALBERT model has 12 hidden layers and 2 hidden groups, with two inner groups, there
            is a total of 4 different layers.

            These layers are flattened: the indices [0,1] correspond to the two inner groups of the first hidden layer,
            while [2,3] correspond to the two inner groups of the second hidden layer.

            Any layer with in index other than [0,1,2,3] will result in an error.
            See base class PreTrainedModel for more information about head pruning
        """
        for layer, heads in heads_to_prune.items():
            group_idx = int(layer / self.config.inner_group_num)
            inner_group_idx = int(layer - group_idx * self.config.inner_group_num)
            self.encoder.albert_layer_groups[group_idx].albert_layers[inner_group_idx].attention.prune_heads(heads)

    def forward(
            self,
            encoder_states,
            input_ids=None,
            src_attention_mask=None,
            tgt_attention_mask=None,
            token_type_ids=None,
            position_ids=None,
            head_mask=None,
            inputs_embeds=None,
    ):
        if input_ids is not None and inputs_embeds is not None:
            raise ValueError("You cannot specify both input_ids and inputs_embeds at the same time")
        elif input_ids is not None:
            input_shape = input_ids.size()
        elif inputs_embeds is not None:
            input_shape = inputs_embeds.size()[:-1]
        else:
            raise ValueError("You have to specify either input_ids or inputs_embeds")

        device = input_ids.device if input_ids is not None else inputs_embeds.device

        if src_attention_mask is None:
            src_attention_mask = torch.ones(input_shape, device=device)
        if token_type_ids is None:
            token_type_ids = torch.zeros(input_shape, dtype=torch.long, device=device)

        extended_src_attention_mask = src_attention_mask.unsqueeze(1).unsqueeze(2)
        extended_src_attention_mask = extended_src_attention_mask.to(
            dtype=next(self.parameters()).dtype)  # fp16 compatibility
        extended_src_attention_mask = (1.0 - extended_src_attention_mask) * -10000.0

        extended_tgt_attention_mask = tgt_attention_mask.unsqueeze(1).unsqueeze(2)
        extended_tgt_attention_mask = extended_tgt_attention_mask.to(
            dtype=next(self.parameters()).dtype)  # fp16 compatibility
        extended_tgt_attention_mask = (1.0 - extended_tgt_attention_mask) * -10000.0

        if head_mask is not None:
            if head_mask.dim() == 1:
                head_mask = head_mask.unsqueeze(0).unsqueeze(0).unsqueeze(-1).unsqueeze(-1)
                head_mask = head_mask.expand(self.config.num_hidden_layers, -1, -1, -1, -1)
            elif head_mask.dim() == 2:
                head_mask = (
                    head_mask.unsqueeze(1).unsqueeze(-1).unsqueeze(-1)
                )  # We can specify head_mask for each layer
            head_mask = head_mask.to(
                dtype=next(self.parameters()).dtype
            )  # switch to fload if need + fp16 compatibility
        else:
            head_mask = [None] * self.config.num_hidden_layers

        embedding_output = self.embeddings(
            input_ids, position_ids=position_ids, token_type_ids=token_type_ids, inputs_embeds=inputs_embeds
        )
        encoder_outputs = self.decoder(encoder_states, embedding_output, extended_src_attention_mask,
                                       extended_tgt_attention_mask, head_mask=head_mask)

        sequence_output = encoder_outputs[0]

        pooled_output = self.pooler_activation(self.pooler(sequence_output[:, 0]))

        # add hidden_states and attentions if they are here
        outputs = (sequence_output, pooled_output) + encoder_outputs[1:]
        return outputs