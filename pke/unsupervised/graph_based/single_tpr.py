# -*- coding: utf-8 -*-
# Author: Florian Boudin
# Date: 09-11-2018

"""Single Topical PageRank keyphrase extraction model.

Graph-based ranking approach to keyphrase extraction described in:

* Lucas Sterckx, Thomas Demeester, Johannes Deleu and Chris Develder.
  Topical Word Importance for Fast Keyphrase Extraction.
  *In proceedings of WWW*, pages 121-122, 2015.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from pke.unsupervised import SingleRank

import os
import six
import gzip
import pickle

import numpy as np
import networkx as nx

from nltk.corpus import stopwords

from scipy.spatial.distance import cosine

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation


class TopicalPageRank(SingleRank):
    """Single TopicalPageRank keyphrase extraction model. 

    Parameterized example::

        import pke
        from nltk.corpus import stopwords

        # 1. create a TopicalPageRank extractor.
        extractor = pke.unsupervised.TopicalPageRank(input_file='path/to/input')

        # 2. load the content of the document.
        extractor.read_document(format='corenlp')

        # 3. select the noun phrases as keyphrase candidates.
        grammar = "NP:{<JJ.*>*<NN.*>+}"
        extractor.candidate_selection(grammar=grammar)

        # 4. weight the keyphrase candidates using Topical PageRank. Builds a
        #    word-graph in which nodes are words with POS and edges are weighted
        #    using the window of words.
        window = 10
        pos = set(['NN', 'NNS', 'NNP', 'NNPS', 'JJ', 'JJR', 'JJS'])
        lda_model = 'path/to/lda_model' 
        stoplist = stopwords.words('english')
        extractor.candidate_weighting(self,
                            window=window,
                            pos=pos,
                            lda_model=lda_model,
                            stoplist=stoplist)

        # 5. get the 10-highest scored candidates as keyphrases
        keyphrases = extractor.get_n_best(n=10)

    """

    def __init__(self, input_file=None, language='english'):
        """Redefining initializer for TopicalPageRank.

        Args:
            input_file (str): path to the input file, defaults to None.
            language (str): language of the document, used for stopwords list,
                default to 'english'.

        """

        super(TopicalPageRank, self).__init__(input_file=input_file,
                                              language=language)


    def candidate_selection(self, grammar=None):
        """Candidate selection heuristic.

        Keyphrase candidates are noun phrases that match the regular expression
        (adjective)*(noun)+, which represents zero or more adjectives followed
        by one or more nouns (Liu et al., 2010).

        Args:
            grammar (str): grammar defining POS patterns of NPs, defaults to 
                "NP: {<JJ.*>*<NN.*>+}".

        """

        # define default NP grammar if none provided
        if grammar is None:
            grammar = "NP:{<JJ.*>*<NN.*>+}"

        # select sequence of adjectives and nouns
        self.grammar_selection(grammar=grammar)


    def candidate_weighting(self,
                            window=10,
                            pos=None,
                            lda_model=None,
                            stoplist=None,
                            normalized=False):
        """Candidate weight calculation using random walk.

        Args:
            window (int): the window within the sentence for connecting two
                words in the graph, defaults to 10.
            pos (set): the set of valid pos for words to be considered as
                nodes in the graph, defaults to (NN, NNS, NNP, NNPS, JJ,
                JJR, JJS).
            lda_model (pickle.gz): an LDA model produced by sklearn in
                pickle compressed (.gz) format
            stoplist (list): the stoplist for filtering words in LDA, defaults
                to the nltk stoplist.
            normalized (False): normalize keyphrase score by their length,
                defaults to False.

        """

        # define default pos tags set
        if pos is None:
            pos = set(['NN', 'NNS', 'NNP', 'NNPS', 'JJ', 'JJR', 'JJS'])

        # initialize stoplist list if not provided
        if stoplist is None:
            stoplist = stopwords.words(self.language)

        # build the word graph
        # ``Since keyphrases are usually noun phrases, we only add adjectives
        # and nouns in word graph.'' -> (Liu et al., 2010)
        self.build_word_graph(window=window, pos=pos)

        # create a blank model
        model = LatentDirichletAllocation()

        # set the default LDA model if none provided
        if lda_model is None:
            if six.PY2:
                lda_model = os.path.join(self._models,
                                     "lda-1000-semeval2010.py2.pickle.gz")
            else:
                lda_model = os.path.join(self._models,
                                     "lda-1000-semeval2010.py3.pickle.gz")

        # load parameters from file
        with gzip.open(lda_model, 'rb') as f:
            (dictionary,
             model.components_,
             model.exp_dirichlet_component_,
             model.doc_topic_prior_) = pickle.load(f)

        # build the document representation
        doc = []
        for s in self.sentences:
            doc.extend([s.stems[i] for i in range(s.length)])

        # vectorize document
        tf_vectorizer = CountVectorizer(stop_words=stoplist,
                                        vocabulary=dictionary)

        tf = tf_vectorizer.fit_transform([' '.join(doc)])

        # compute the topic distribution over the document
        distribution_topic_document = model.transform(tf)[0]

        # compute the word distributions over topics
        distributions = model.components_ / model.components_.sum(axis=1)[:, np.newaxis]

        # compute the topical word importance
        twi = {}
        for word in self.graph.nodes():
            if word in dictionary:
                index = dictionary.index(word)
                distribution_word_topic = [distributions[k][index] for k \
                                     in range(len(distribution_topic_document))]

                twi[word] = 1 - cosine(distribution_word_topic,
                                       distribution_topic_document)

        # assign default probabilities to OOV words
        default_similarity = min(twi.values())
        for word in self.graph.nodes():
            if word not in twi:
                twi[word] = default_similarity

        # normalize the probabilities
        norm = sum(twi.values())
        for word in twi:
            twi[word] /= norm

        # compute the word scores using biaised random walk
        w = nx.pagerank(G=self.graph,
                        alpha=0.85,
                        personalization=twi,
                        max_iter=100,
                        weight='weight')

        # loop through the candidates
        for k in self.candidates.keys():
            tokens = self.candidates[k].lexical_form
            self.weights[k] = sum([w[t] for t in tokens])
            if normalized:
                self.weights[k] /= len(tokens)

