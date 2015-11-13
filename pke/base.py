# -*- coding: utf-8 -*-

import re

from corenlp_parser import MinimalCoreNLPParser

from collections import defaultdict

from nltk.stem.snowball import SnowballStemmer as stemmer
from nltk.corpus import stopwords

class Sentence:
    """ The sentence data structure. """

    def __init__(self, words):

        self.words = words
        """ tokens as a list. """

        self.POS = []
        """ Part-Of-Speeches as a list. """

        self.stems = []
        """ stems as a list. """

        self.length = len(words)
        """ length of the sentence. """


class Candidate:
    """ The keyphrase candidate data structure. """

    def __init__(self):

        self.surface_forms = []
        """ the surface forms of the candidate. """

        self.offsets = []
        """ the offsets of the surface forms. """

        self.lexical_form = []
        """ the lexical form of the candidate. """


class LoadFile(object):
    """ The LoadFile class that provides base functions. """

    def __init__(self, input_file):
        """ Initializer for LoadFile class.

            Args:
                input_file (str): the path of the input file.
        """

        self.input_file = input_file
        """ The path of the input file. """

        self.sentences = []
        """ The sentence container (list of Sentence). """

        self.candidates = defaultdict(Candidate)
        """ The candidate container (dict of Candidate). """

        self.weights = {}
        """ The weight container (can be either word or candidate weights). """


    def read_corenlp_document(self, use_lemmas=True, stemming="porter"):
        """ Read the input file in CoreNLP XML format and populate the sentence
            list.

            Args:
                use_lemmas (bool): weither lemmas from stanford corenlp are used
                    instead of stems (computed by nltk), defaults to True.
                stemming (str): the language of the stemming (if used), defaults
                    to porter.
        """

        parse = MinimalCoreNLPParser(self.input_file)

        for i, sentence in enumerate(parse.sentences):
            s = Sentence(words=sentence["words"])
            s.POS = sentence["POS"]
            if use_lemmas:
                s.stems = [t.lower() for t in sentence["lemmas"]]
            else:
                s.stems = [stemmer(stemming).stem(t.lower()) for t in s.words]
            self.sentences.append(s)


    def get_n_best(self, n=10):
        """ Returns the n-best candidates given the weights. """

        best = sorted(self.weights, key=self.weights.get, reverse=True)
        return [(u, self.weights[u]) for u in best[:min(n, len(best))]]


    def ngram_selection(self, n=3):
        """ Select all the n-grams and populate the candidate container. 

            Args:
                n (int): the n-gram length, defaults to 3.
        """

        for i, sentence in enumerate(self.sentences):

            skip = min(n, sentence.length)
            shift = sum([s.length for s in self.sentences[0:i]])

            for j in range(sentence.length):
                for k in range(j+1, min(j+1+skip, sentence.length+1)):

                    surface_form = sentence.words[j:k]
                    norm_form = sentence.stems[j:k]
                    lex_form = ' '.join(norm_form)

                    self.candidates[lex_form].surface_forms.append(surface_form)
                    self.candidates[lex_form].lexical_form = norm_form
                    self.candidates[lex_form].offsets.append(shift+j)


    def sequence_selection(self, pos=['NN', 'NNS', 'NNP', 'NNPS', 
                                      'JJ', 'JJR', 'JJS']):
        """ Select all the n-grams and populate the candidate container. 

            Args:
                n (int): the n-gram length, defaults to 3.
        """

        for i, sentence in enumerate(self.sentences):

            shift = sum([s.length for s in self.sentences[0:i]])
            seq = []

            for j in range(sentence.length):

                # add candidate offset in sequence and continue if not last word
                if sentence.POS[j] in pos:
                    seq.append(j)
                    if j < (sentence.length - 1):
                        continue

                # add candidate
                if seq:
                    surface_form = sentence.words[seq[0]:seq[-1]+1]
                    norm_form = sentence.stems[seq[0]:seq[-1]+1]
                    lex_form = ' '.join(norm_form)
                    self.candidates[lex_form].surface_forms.append(surface_form)
                    self.candidates[lex_form].lexical_form = norm_form
                    self.candidates[lex_form].offsets.append(shift+j)

                # flush sequence container
                seq = []


    def candidate_filtering(self, stoplist=[]):
        """ Filter the candidates containing strings from the stoplist.

            Args:
                stoplist (list): list of strings, defaults to empty.
        """

        for k, v in self.candidates.items():
            words = [u.lower() for u in v.surface_forms[0]]
            if set(words).intersection(stoplist):
                del self.candidates[k]











