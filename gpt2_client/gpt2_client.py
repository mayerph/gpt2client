#!/usr/bin/env python3

import os
from termcolor import colored, cprint
import requests
import sys
from tqdm import tqdm
import json
import json
import regex as re

import tensorflow as tf
from tensorflow.contrib.training import HParams
import numpy as np
import gpt_2_simple as gpt2

try:
    from functools import lru_cache
except ImportError:
    from backports.functools_lru_cache import lru_cache

class GPT2Client(object):
    def __init__(self, model_name='124M', save_dir='models'):
        """
        Attributes
        ----------
        attr: model_name (string)
        - default: '124M'
        - desc: Downloads the '124M' GPT-2 model. Can alternatively be set to the '355M', '774M', or '1558M' model

        attr: save_dir (string)
        - default: 'models'
        - desc: Name of directory where the weights, checkpoints, and 
                hyper-parameters are downloaded and saved
                
        Methods
        -------
        download_helper(filename : string)
        load_model(force_download : bool)
        generate(interactive : bool, n_samples : int, words : int, display : bool, return_text: bool) -> list of string
        generate_batch_from_prompts(prompts : list) -> list of string
        fintune(corpus : object, return_text : bool) -> text
        encode_seq(sequence : string) -> numpy array of integer
        decode_seq(sequence : integers) -> list of string
        """
        
        assert model_name in ['124M', '355M', '774M', '1558M'], 'Please choose from either 124M, 355M, 774M, or 1558M parameter models only. This library does support other model sizes.'
        assert save_dir != '', 'Please provide a save directory for the model weights and checkpoints. This cannot be empty.'

        self.model_name = model_name
        self.save_dir = save_dir
        
    def download_helper(self, filename):
        r = requests.get('https://openaipublic.blob.core.windows.net/gpt-2/models/' + self.model_name + '/' + filename, stream=True)
        
        with open("./{}/{}/{}".format(self.save_dir, self.model_name, filename), 'wb') as f:
            file_size = int(r.headers['content-length'])
            chunk_size = 1000
            with tqdm(ncols=100, desc='Downloading {}'.format(colored(filename, 'cyan', attrs=['bold'])), total=file_size, unit_scale=True) as pbar:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    pbar.update(chunk_size)

    def load_model(self, force_download=False):
        """ Creates `models` directory and downloads model weights and checkpoints

        Parameters
        ----------
        arg: force_download (bool)
            - default: False
            - desc: Ignore cached files and redownload model weights and checkpoints when set to `True`
        """
        
        subdir = "./{}/{}/".format(self.save_dir, self.model_name)
        if os.path.exists(subdir) == False:
            os.makedirs(subdir)
            print ('Created `{}/{}` directory to save model weights and checkpoints.'.format(self.save_dir, self.model_name))
            
        if force_download == True:
            for filename in ['checkpoint', 'encoder.json', 'hparams.json', 'model.ckpt.data-00000-of-00001', 'model.ckpt.index', 'model.ckpt.meta', 'vocab.bpe']:
                self.download_helper(filename)
        else:
            for filename in ['checkpoint', 'encoder.json', 'hparams.json', 'model.ckpt.data-00000-of-00001', 'model.ckpt.index', 'model.ckpt.meta', 'vocab.bpe']:
                if os.path.exists(subdir + filename):
                    print ('{0:<60}{1:<20}'.format("Loading " + colored(filename, 'cyan', attrs=['bold']), "File already exists"))
                else:
                    self.download_helper(filename)

    def generate(self, interactive=False, n_samples=1, words=None, display=True, return_text=False):
        """ Returns generated text sample
        
        Parameters
        ----------
        arg: interactive (bool)
            - default: False
            - desc: Toggles interactive mode which prompts user for input text

        arg: n_samples (int)
            - default: 0
            - desc: Number of samples to be generated by GPT-2 Model. If 0, it generates indefinitely
     
        arg: words (int)
            - default=None
            - desc: Number of words generated by the client

        arg: display (bool)
            - default: True
            - desc: Prints out text to console when set to True

        arg: return_text (bool)
            - default: False
            - desc: Returns generated text when set to True

        Returns:
            An array of generated strings
        """
        
        models_dir = models_dir = os.path.expanduser(os.path.expandvars(self.save_dir))
        enc = get_encoder(self.model_name, self.save_dir)
        hparams = default_hparams()

        with open(os.path.join(self.save_dir, self.model_name, 'hparams.json')) as f:
            data = json.load(f)
            hparams.override_from_dict(data)

        length = hparams.n_ctx

        with tf.Session(graph=tf.Graph()) as sess:
            batch_size = 1
            temperature = 1
            top_k = 40

            context = tf.placeholder(tf.int32, [batch_size, None])
            np.random.seed(None)
            tf.set_random_seed(None)

            output = sample_sequence(
                hparams=hparams,
                length=length,
                start_token=enc.encoder['<|endoftext|>'],
                batch_size=batch_size,
                temperature=temperature, 
                top_k=top_k
            )

            saver = tf.train.Saver()
            ckpt = tf.train.latest_checkpoint(os.path.join(self.save_dir, self.model_name))
            saver.restore(sess, ckpt)

            if not interactive:
                # Generate random samples from scratch
                print (colored('Generating sample...', 'yellow'))
                
                #must initialize generated...
                generated = 0

                while n_samples == 0 or generated < n_samples:
                    out = sess.run(output)
                    for i in range(batch_size):
                        generated += batch_size
                        text.append(enc.decode(out[i]))
                        print (colored('---------------------SAMPLE---------------------\n', 'cyan'))

                        if display:
                            print (text)

                        if return_text:
                            return text

            else:
                # Generate random samples from prompt
                for _ in range(n_samples):
                    prompt = input(colored('Enter a prompt got GPT-2 >> ', 'cyan'))
                    print ('{}: {}\n'.format(colored('Prompt', attrs=['bold']), colored(prompt, 'green')))
                    print (colored('Generating sample...', 'yellow'))

                    context_tokens = enc.encode(prompt)
                    text_array = []
                    text = ''
                    generated = 0
                    for _ in range(n_samples // batch_size):
                        out = sess.run(output, feed_dict={
                            context: [context_tokens for _ in range(batch_size)]
                        })[:, len(context_tokens):]

                        for i in range(batch_size):
                            generated += 1
                            text += enc.decode(out[i])
                            text_array.append(enc.decode(out[i]))
                            print (colored('---------------------SAMPLE---------------------\n', 'cyan'))

                            if display:
                                print (text)

                            if return_text:
                                return text_array

    def generate_batch_from_prompts(self, batch):
        """ Returns an array of generated text

        Parameters
        ----------
        arg: batch (list)
            - desc: An array of prompts given to the GPT2Client instance.
                    The contents of the array are fed to the instance one by one

        Returns:
            An array of generated text for each prompt given in `batch`
        """                
        
        final_generated_text = []
        
        models_dir = models_dir = os.path.expanduser(os.path.expandvars(self.save_dir))
        enc = get_encoder(self.model_name, self.save_dir)
        hparams = default_hparams()

        with open(os.path.join(self.save_dir, self.model_name, 'hparams.json')) as f:
            data = json.load(f)
            hparams.override_from_dict(data)

        length = hparams.n_ctx

        with tf.Session(graph=tf.Graph()) as sess:
            batch_size = 1
            temperature = 1
            top_k = 40

            context = tf.placeholder(tf.int32, [batch_size, None])
            np.random.seed(None)
            tf.set_random_seed(None)

            output = sample_sequence(
                hparams=hparams,
                length=length,
                start_token=enc.encoder['<|endoftext|>'],
                batch_size=batch_size,
                temperature=temperature, 
                top_k=top_k
            )

            saver = tf.train.Saver()
            ckpt = tf.train.latest_checkpoint(os.path.join(self.save_dir, self.model_name))
            saver.restore(sess, ckpt)
        
            for i in batch:
                print ('Prompt: {}'.format(colored(i, 'green')))
                context_tokens = enc.encode(i)
                text_array = []
                text = ''
                generated = 0
                for _ in range(len(batch) // batch_size):
                    out = sess.run(output, feed_dict={
                        context: [context_tokens for _ in range(batch_size)]
                    })[:, len(context_tokens):]

                    for i in range(batch_size):
                        generated += 1
                        text += enc.decode(out[i])
                        
                        final_generated_text.append(enc.decode(out[i]))
                
        return final_generated_text

    def finetune(self, corpus, return_text=True):
        """ Returns generated text sample

        Parameters
        ----------
        arg: corpus (object)
            - desc: Custom dataset text file

        arg: return_text (bool)
            - default: True
            - desc: Toggles whether to return custom-generated text in an array after fine-tuning

        Returns:
            Generated string in an array
        """
        sess = gpt2.start_tf_sess()
        gpt2.finetune(sess,
                corpus,
                model_name=self.model_name,
                steps=1000)     # steps is max number of training steps

        if return_text:
            text = gpt2.generate(sess, return_as_list=True)
            return text
        else:
            gpt2.generate(sess)	
                 
    def encode_seq(self, sequence):
        models_dir = models_dir = os.path.expanduser(os.path.expandvars(self.save_dir))
        enc = get_encoder(self.model_name, self.save_dir)
        hparams = default_hparams()

        with open(os.path.join(self.save_dir, self.model_name, 'hparams.json')) as f:
            data = json.load(f)
            hparams.override_from_dict(data)
        
        length = hparams.n_ctx

        with tf.Session(graph=tf.Graph()) as sess:
            batch_size = 1
            temperature = 1
            top_k = 40

            context = tf.placeholder(tf.int32, [batch_size, None])
            np.random.seed(None)
            tf.set_random_seed(None)

            output = sample_sequence(
                hparams=hparams,
                length=length,
                start_token=enc.encoder['<|endoftext|>'],
                batch_size=batch_size,
                temperature=temperature, 
                top_k=top_k
            )

            saver = tf.train.Saver()
            ckpt = tf.train.latest_checkpoint(os.path.join(self.save_dir, self.model_name))
            saver.restore(sess, ckpt)
            
            context_tokens = enc.encode(sequence)
            content_tokens = np.array(content_tokens)
            
            return context_tokens
        
    def decode_seq(self, encodings):
        # converting numpy array to list
        if type(encodings).__module__ == np.__name__:
            encodings = encodings.tolist()

        models_dir = models_dir = os.path.expanduser(os.path.expandvars(self.save_dir))
        enc = get_encoder(self.model_name, self.save_dir)
        hparams = default_hparams()

        with open(os.path.join(self.save_dir, self.model_name, 'hparams.json')) as f:
            data = json.load(f)
            hparams.override_from_dict(data)
            
        length = hparams.n_ctx

        with tf.Session(graph=tf.Graph()) as sess:
            batch_size = 1
            temperature = 1
            top_k = 40

            context = tf.placeholder(tf.int32, [batch_size, None])
            np.random.seed(None)
            tf.set_random_seed(None)

            output = sample_sequence(
                hparams=hparams,
                length=length,
                start_token=enc.encoder['<|endoftext|>'],
                batch_size=batch_size,
                temperature=temperature, 
                top_k=top_k
            )

            saver = tf.train.Saver()
            ckpt = tf.train.latest_checkpoint(os.path.join(self.save_dir, self.model_name))
            saver.restore(sess, ckpt)
            
            sequences = enc.decode(encodings)
            
            return sequences
            
@lru_cache()
def bytes_to_unicode():
    """
    Returns list of utf-8 byte and a corresponding list of unicode strings.
    The reversible bpe codes work on unicode strings.
    This means you need a large # of unicode characters in your vocab if you want to avoid UNKs.
    When you're at something like a 10B token dataset you end up needing around 5K for decent coverage.
    This is a signficant percentage of your normal, say, 32K bpe vocab.
    To avoid that, we want lookup tables between utf-8 bytes and unicode strings.
    And avoids mapping to whitespace/control characters the bpe code barfs on.
    """
    bs = list(range(ord("!"), ord("~")+1))+list(range(ord("¡"), ord("¬")+1))+list(range(ord("®"), ord("ÿ")+1))
    cs = bs[:]
    n = 0
    for b in range(2**8):
        if b not in bs:
            bs.append(b)
            cs.append(2**8+n)
            n += 1
    cs = [chr(n) for n in cs]
    return dict(zip(bs, cs))

def get_pairs(word):
    """Return set of symbol pairs in a word.

    Word is represented as tuple of symbols (symbols being variable-length strings).
    """
    pairs = set()
    prev_char = word[0]
    for char in word[1:]:
        pairs.add((prev_char, char))
        prev_char = char
    return pairs

class Encoder:
    def __init__(self, encoder, bpe_merges, errors='replace'):
        self.encoder = encoder
        self.decoder = {v:k for k,v in self.encoder.items()}
        self.errors = errors # how to handle errors in decoding
        self.byte_encoder = bytes_to_unicode()
        self.byte_decoder = {v:k for k, v in self.byte_encoder.items()}
        self.bpe_ranks = dict(zip(bpe_merges, range(len(bpe_merges))))
        self.cache = {}

        # Should haved added re.IGNORECASE so BPE merges can happen for capitalized versions of contractions
        self.pat = re.compile(r"""'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+""")

    def bpe(self, token):
        if token in self.cache:
            return self.cache[token]
        word = tuple(token)
        pairs = get_pairs(word)

        if not pairs:
            return token

        while True:
            bigram = min(pairs, key = lambda pair: self.bpe_ranks.get(pair, float('inf')))
            if bigram not in self.bpe_ranks:
                break
            first, second = bigram
            new_word = []
            i = 0
            while i < len(word):
                try:
                    j = word.index(first, i)
                    new_word.extend(word[i:j])
                    i = j
                except:
                    new_word.extend(word[i:])
                    break

                if word[i] == first and i < len(word)-1 and word[i+1] == second:
                    new_word.append(first+second)
                    i += 2
                else:
                    new_word.append(word[i])
                    i += 1
            new_word = tuple(new_word)
            word = new_word
            if len(word) == 1:
                break
            else:
                pairs = get_pairs(word)
        word = ' '.join(word)
        self.cache[token] = word
        return word

    def encode(self, text):
        bpe_tokens = []
        for token in re.findall(self.pat, text):
            token = ''.join(self.byte_encoder[b] for b in token.encode('utf-8'))
            bpe_tokens.extend(self.encoder[bpe_token] for bpe_token in self.bpe(token).split(' '))
        return bpe_tokens

    def decode(self, tokens):
        text = ''.join([self.decoder[token] for token in tokens])
        text = bytearray([self.byte_decoder[c] for c in text]).decode('utf-8', errors=self.errors)
        return text

def get_encoder(model_name, models_dir):
    with open("./{}/{}/".format(models_dir, model_name) + 'encoder.json', 'r') as f:
        encoder = json.load(f)
    with open("./{}/{}/".format(models_dir, model_name) + 'vocab.bpe', 'r', encoding="utf-8") as f:
        bpe_data = f.read()
    bpe_merges = [tuple(merge_str.split()) for merge_str in bpe_data.split('\n')[1:-1]]
    return Encoder(
        encoder=encoder,
        bpe_merges=bpe_merges,
    )

def top_k_logits(logits, k):
    if k == 0:
        # no truncation
        return logits

    def _top_k():
        values, _ = tf.nn.top_k(logits, k=k)
        min_values = values[:, -1, tf.newaxis]
        return tf.where(
            logits < min_values,
            tf.ones_like(logits, dtype=logits.dtype) * -1e10,
            logits,
        )
    return tf.cond(
         tf.equal(k, 0),
         lambda: logits,
         lambda: _top_k(),
    )

def sample_sequence(hparams, length, start_token=None, batch_size=None, context=None, temperature=1, top_k=0):
    if start_token is None:
        assert context is not None, 'Specify exactly one of start_token and context!'
    else:
        assert context is None, 'Specify exactly one of start_token and context!'
        context = tf.fill([batch_size, 1], start_token)

    def step(hparams, tokens, past=None):
        lm_output = model(hparams=hparams, X=tokens, past=past, reuse=tf.AUTO_REUSE)

        logits = lm_output['logits'][:, :, :hparams.n_vocab]
        presents = lm_output['present']
        presents.set_shape(past_shape(hparams=hparams, batch_size=batch_size))
        return {
            'logits': logits,
            'presents': presents,
        }

    with tf.name_scope('sample_sequence'):
        def body(past, prev, output):
            next_outputs = step(hparams, prev, past=past)
            logits = next_outputs['logits'][:, -1, :]    / tf.to_float(temperature)
            logits = top_k_logits(logits, k=top_k)
            samples = tf.multinomial(logits, num_samples=1, output_dtype=tf.int32)
            return [
                next_outputs['presents'] if past is None else tf.concat([past, next_outputs['presents']], axis=-2),
                samples,
                tf.concat([output, samples], axis=1)
            ]

        past, prev, output = body(None, context, context)

        def cond(*args):
            return True

        _, _, tokens = tf.while_loop(
            cond=cond, body=body,
            maximum_iterations=length - 1,
            loop_vars=[
                past,
                prev,
                output
            ],
            shape_invariants=[
                tf.TensorShape(past_shape(hparams=hparams, batch_size=batch_size)),
                tf.TensorShape([batch_size, None]),
                tf.TensorShape([batch_size, None]),
            ],
            back_prop=False,
        )

        return tokens

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)

def default_hparams():
    return HParams(
        n_vocab=0,
        n_ctx=1024,
        n_embd=768,
        n_head=12,
        n_layer=12,
    )

def shape_list(x):
    """Deal with dynamic shape in tensorflow cleanly."""
    static = x.shape.as_list()
    dynamic = tf.shape(x)
    return [dynamic[i] if s is None else s for i, s in enumerate(static)]

def softmax(x, axis=-1):
    x = x - tf.reduce_max(x, axis=axis, keepdims=True)
    ex = tf.exp(x)
    return ex / tf.reduce_sum(ex, axis=axis, keepdims=True)

def gelu(x):
    return 0.5*x*(1+tf.tanh(np.sqrt(2/np.pi)*(x+0.044715*tf.pow(x, 3))))

def norm(x, scope, axis=-1, epsilon=1e-5):
    """Normalize to mean = 0, std = 1, then do a diagonal affine transform."""
    with tf.variable_scope(scope):
        n_state = x.shape[-1].value
        g = tf.get_variable('g', [n_state], initializer=tf.constant_initializer(1))
        b = tf.get_variable('b', [n_state], initializer=tf.constant_initializer(0))
        u = tf.reduce_mean(x, axis=axis, keepdims=True)
        s = tf.reduce_mean(tf.square(x-u), axis=axis, keepdims=True)
        x = (x - u) * tf.rsqrt(s + epsilon)
        x = x*g + b
        return x

def split_states(x, n):
    """Reshape the last dimension of x into [n, x.shape[-1]/n]."""
    *start, m = shape_list(x)
    return tf.reshape(x, start + [n, m//n])

def merge_states(x):
    """Smash the last two dimensions of x into a single dimension."""
    *start, a, b = shape_list(x)
    return tf.reshape(x, start + [a*b])

def conv1d(x, scope, nf, w_init_stdev=0.02):
    with tf.variable_scope(scope):
        *start, nx = shape_list(x)
        w = tf.get_variable('w', [1, nx, nf], initializer=tf.random_normal_initializer(stddev=w_init_stdev))
        b = tf.get_variable('b', [nf], initializer=tf.constant_initializer(0))
        c = tf.reshape(tf.matmul(tf.reshape(x, [-1, nx]), tf.reshape(w, [-1, nf]))+b, start+[nf])
        return c

def attention_mask(nd, ns, dtype):
    """1's in the lower triangle, counting from the lower right corner.

    Same as tf.matrix_band_part(tf.ones([nd, ns]), -1, ns-nd), but doesn't produce garbage on TPUs.
    """
    i = tf.range(nd)[:,None]
    j = tf.range(ns)
    m = i >= j - ns + nd
    return tf.cast(m, dtype)

def attn(x, scope, n_state, past, hparams):
    assert x.shape.ndims == 3    # Should be [batch, sequence, features]
    assert n_state % hparams.n_head == 0
    if past is not None:
        assert past.shape.ndims == 5    # Should be [batch, 2, heads, sequence, features], where 2 is [k, v]

    def split_heads(x):
        # From [batch, sequence, features] to [batch, heads, sequence, features]
        return tf.transpose(split_states(x, hparams.n_head), [0, 2, 1, 3])

    def merge_heads(x):
        # Reverse of split_heads
        return merge_states(tf.transpose(x, [0, 2, 1, 3]))

    def mask_attn_weights(w):
        # w has shape [batch, heads, dst_sequence, src_sequence], where information flows from src to dst.
        _, _, nd, ns = shape_list(w)
        b = attention_mask(nd, ns, dtype=w.dtype)
        b = tf.reshape(b, [1, 1, nd, ns])
        w = w*b - tf.cast(1e10, w.dtype)*(1-b)
        return w

    def multihead_attn(q, k, v):
        # q, k, v have shape [batch, heads, sequence, features]
        w = tf.matmul(q, k, transpose_b=True)
        w = w * tf.rsqrt(tf.cast(v.shape[-1].value, w.dtype))

        w = mask_attn_weights(w)
        w = softmax(w)
        a = tf.matmul(w, v)
        return a

    with tf.variable_scope(scope):
        c = conv1d(x, 'c_attn', n_state*3)
        q, k, v = map(split_heads, tf.split(c, 3, axis=2))
        present = tf.stack([k, v], axis=1)
        if past is not None:
            pk, pv = tf.unstack(past, axis=1)
            k = tf.concat([pk, k], axis=-2)
            v = tf.concat([pv, v], axis=-2)
        a = multihead_attn(q, k, v)
        a = merge_heads(a)
        a = conv1d(a, 'c_proj', n_state)
        return a, present

def mlp(x, scope, n_state, hparams):
    with tf.variable_scope(scope):
        nx = x.shape[-1].value
        h = gelu(conv1d(x, 'c_fc', n_state))
        h2 = conv1d(h, 'c_proj', nx)
        return h2

def block(x, scope, past, hparams):
    with tf.variable_scope(scope):
        nx = x.shape[-1].value
        a, present = attn(norm(x, 'ln_1'), 'attn', nx, past=past, hparams=hparams)
        x = x + a
        m = mlp(norm(x, 'ln_2'), 'mlp', nx*4, hparams=hparams)
        x = x + m
        return x, present

def past_shape(hparams, batch_size=None, sequence=None):
    return [batch_size, hparams.n_layer, 2, hparams.n_head, sequence, hparams.n_embd // hparams.n_head]

def expand_tile(value, size):
    """Add a new axis of given size."""
    value = tf.convert_to_tensor(value, name='value')
    ndims = value.shape.ndims
    return tf.tile(tf.expand_dims(value, axis=0), [size] + [1]*ndims)

def positions_for(tokens, past_length):
    batch_size = tf.shape(tokens)[0]
    nsteps = tf.shape(tokens)[1]
    return expand_tile(past_length + tf.range(nsteps), batch_size)

def model(hparams, X, past=None, scope='model', reuse=False):
    with tf.variable_scope(scope, reuse=reuse):
        results = {}
        batch, sequence = shape_list(X)

        wpe = tf.get_variable('wpe', [hparams.n_ctx, hparams.n_embd],
                             initializer=tf.random_normal_initializer(stddev=0.01))
        wte = tf.get_variable('wte', [hparams.n_vocab, hparams.n_embd],
                             initializer=tf.random_normal_initializer(stddev=0.02))
        past_length = 0 if past is None else tf.shape(past)[-2]
        h = tf.gather(wte, X) + tf.gather(wpe, positions_for(X, past_length))

        # Transformer
        presents = []
        pasts = tf.unstack(past, axis=1) if past is not None else [None] * hparams.n_layer
        assert len(pasts) == hparams.n_layer
        for layer, past in enumerate(pasts):
            h, present = block(h, 'h%d' % layer, past=past, hparams=hparams)
            presents.append(present)
        results['present'] = tf.stack(presents, axis=1)
        h = norm(h, 'ln_f')

        # Language model loss. Do tokens <n predict token n?
        h_flat = tf.reshape(h, [batch*sequence, hparams.n_embd])
        logits = tf.matmul(h_flat, wte, transpose_b=True)
        logits = tf.reshape(logits, [batch, sequence, hparams.n_vocab])
        results['logits'] = logits
        return results
