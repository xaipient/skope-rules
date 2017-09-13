"""
Rk (to be explained to scikit-contrib):
Some classifiers tests failing (that's why we do not inherit from
ClassifierMixin, then all the tests are passing):

-check_classifier_classes
due to multiclass classification testing

-check_classifiers_train
due to multiclass classification testing (make_blobs generate 3 classes)
and also due to requirement "pred = decision > 0", which is in contradiction
with the bigger is better (here less abnormal) convention: in our case, we
have pred = decision < 0
"""

import pdb
import numpy as np
import pandas  # XXX to be rm
import numbers
from warnings import warn
from sklearn.base import BaseEstimator
from sklearn.utils.validation import check_X_y, check_array, check_is_fitted
from sklearn.utils.multiclass import check_classification_targets

from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from sklearn.ensemble import BaggingClassifier, BaggingRegressor

from sklearn.externals import six
from sklearn.tree import _tree

INTEGER_TYPES = (numbers.Integral, np.integer)


class FraudToRules(BaseEstimator):
    """ An easy-interpretable classifier optimizing simple logical rules.

    Parameters
    ----------

    feature_names: list of str, optional
        XXX (remove it if we want generic tool)
        The names of each feature to be used for returning rules in string
        format.

    precision_min: float, optional (default=0.5)
        minimal precision of a rule to be selected.

    recall_min: float, optional (default=0.1)
        minimal recall of a rule to be selected.

    BAGGING PARAMETERS:

    n_estimators : int, optional (default=1)
        The number of base estimators (rules) to use for prediction. More are
        built before selection. All are available in the estimators_ attribute.

    max_samples : int or float, optional (default=1.)
        The number of samples to draw from X to train each decision tree, from
        which rules are generated and selected.
            - If int, then draw `max_samples` samples.
            - If float, then draw `max_samples * X.shape[0]` samples.
        If max_samples is larger than the number of samples provided,
        all samples will be used for all trees (no sampling).

    max_samples_features : int or float, optional (default=1.0)
        The number of features to draw from X to train each decision tree.
            - If int, then draw `max_features` features.
            - If float, then draw `max_features * X.shape[1]` features.

    bootstrap : boolean, optional (default=True)
        Whether samples are drawn with replacement.

    bootstrap_features : boolean, optional (default=False)
        Whether features are drawn with replacement.


    BASE ESTIMATORS PARAMETERS:

    max_depth : integer or None, optional (default=None)
        The maximum depth of the decision trees. If None, then nodes are
        expanded until all leaves are pure or until all leaves contain less
        than min_samples_split samples.  XXX faisable en pratique?

    max_features : int, float, string or None, optional (default="auto")
        The number of features considered (by each decision tree) when looking
        for the best split:

        - If int, then consider `max_features` features at each split.
        - If float, then `max_features` is a percentage and
          `int(max_features * n_features)` features are considered at each
          split.
        - If "auto", then `max_features=sqrt(n_features)`.
        - If "sqrt", then `max_features=sqrt(n_features)` (same as "auto").
        - If "log2", then `max_features=log2(n_features)`.
        - If None, then `max_features=n_features`.

        Note: the search for a split does not stop until at least one
        valid partition of the node samples is found, even if it requires to
        effectively inspect more than ``max_features`` features.

    min_samples_split : int, float, optional (default=2)
        The minimum number of samples required to split an internal node for
        each decision tree.
        - If int, then consider `min_samples_split` as the minimum number.
        - If float, then `min_samples_split` is a percentage and
          `ceil(min_samples_split * n_samples)` are the minimum
          number of samples for each split.

    XXX should we add more DecisionTree params?

    GENERAL PARAMETERS:

    n_jobs : integer, optional (default=1)
        The number of jobs to run in parallel for both `fit` and `predict`.
        If -1, then the number of jobs is set to the number of cores.

    random_state : int, RandomState instance or None, optional (default=None)
        If int, random_state is the seed used by the random number generator;
        If RandomState instance, random_state is the random number generator;
        If None, the random number generator is the RandomState instance used
        by `np.random`.

    verbose : int, optional (default=0)
        Controls the verbosity of the tree building process.

    Attributes
    ----------
    rules_ : dict of tuples (rule, precision, recall, nb).
        The collection of rules generated by fitted sub-estimators (decision
        trees) and further selected according to their respective OOB
        precisions and recalls.
        All rules fulfilling recall_min and precision_min conditions are saved.
        A number n_rules of these rules are selected according to their OOB
        precision.
        The selected rules are used in the ``predict`` method and  can be
        obtained with rules_[:n_estimators].

    estimators_ : list of DecisionTreeClassifier
        The collection of fitted sub-estimators used to generate candidate
        rules.

    estimators_samples_ : list of arrays
        The subset of drawn samples (i.e., the in-bag samples) for each base
        estimator.

    estimators_features_ : list of arrays
        The subset of drawn features for each base estimator.

    max_samples_ : integer
        The actual number of samples

    n_features_ : integer
        The number of features when ``fit`` is performed.

    classes_ : array, shape (n_classes,)
        The classes labels.
    """

    def __init__(self,
                 feature_names=None,
                 precision_min=0.5,
                 recall_min=0.01,
                 n_estimators=1,
                 max_samples=.8,
                 max_samples_features=1.,
                 max_depth=3,
                 max_features=1.,
                 min_samples_split=2,
                 bootstrap=False,
                 bootstrap_features=False,
                 n_jobs=1,
                 random_state=None,
                 verbose=0):
        self.precision_min = precision_min
        self.recall_min = recall_min
        self.feature_names = feature_names
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.max_samples_features = max_samples_features
        self.max_depth = max_depth
        self.max_features = max_features
        self.min_samples_split = min_samples_split
        self.bootstrap = bootstrap
        self.bootstrap_features = bootstrap_features
        self.n_jobs = n_jobs
        self.random_state = random_state
        self.verbose = verbose

    def fit(self, X, y, sample_weight=None):
        """Fit the model according to the given training data.

        Parameters
        ----------
        X : array-like, shape (n_samples, n_features)
            Training vector, where n_samples is the number of samples and
            n_features is the number of features. XXX sparse matrix?

        y : array-like, shape (n_samples,)
            Target vector relative to X. Has to follow the convention 0 for
            normal data, 1 for frauds.
            XXX maybe make such y ourselves from input?

        sample_weight : array-like, shape (n_samples,) optional
            Array of weights that are assigned to individual samples, typically
            the amount in case of transactions data. Used to grow regression
            trees producing further rules to be tested.
            If not provided, then each sample is given unit weight.

        Returns
        -------
        self : object
            Returns self.
        """

        X, y = check_X_y(X, y)
        check_classification_targets(y)
        self.n_features_ = X.shape[1]

        self.classes_ = np.unique(y)
        n_classes = len(self.classes_)

        if n_classes < 2:
            raise ValueError("This method needs samples of at least 2 classes"
                             " in the data, but the data contains only one"
                             " class: %r" % self.classes_[0])

        if not set(self.classes_) == set([0, 1]):
            warn("Found labels %s. This method assumes fraud to be labeled as"
                 " 1 and normal data to be labeled as 0. Any label"
                 " different from 0 will be considered as fraud."
                 % set(self.classes_))

        # ensure that max_samples is in [1, n_samples]:
        n_samples = X.shape[0]

        if isinstance(self.max_samples, six.string_types):
            raise ValueError('max_samples (%s) is not supported.'
                             'Valid choices are: "auto", int or'
                             'float' % self.max_samples)

        elif isinstance(self.max_samples, INTEGER_TYPES):
            if self.max_samples > n_samples:
                warn("max_samples (%s) is greater than the "
                     "total number of samples (%s). max_samples "
                     "will be set to n_samples for estimation."
                     % (self.max_samples, n_samples))
                max_samples = n_samples
            else:
                max_samples = self.max_samples
        else:  # float
            if not (0. < self.max_samples <= 1.):
                raise ValueError("max_samples must be in (0, 1], got %r"
                                 % self.max_samples)
            max_samples = int(self.max_samples * X.shape[0])

        self.max_samples_ = max_samples

        self.rules_ = {}
        self.estimators_ = []
        self.estimators_samples_ = []
        self.estimators_features_ = []

        # default columns names of the form ['c0', 'c1', ...]:
        feature_names_ = (self.feature_names if self.feature_names is not None
                          else ['c' + x for x in
                                np.arange(X.shape[1]).astype(str)])
        self.feature_names_ = feature_names_

        bagging_clf = BaggingClassifier(
            base_estimator=DecisionTreeClassifier(
                max_depth=self.max_depth,
                max_features=self.max_features,
                min_samples_split=self.min_samples_split),
            n_estimators=self.n_estimators,
            max_samples=self.max_samples_,
            max_features=self.max_samples_features,
            bootstrap=self.bootstrap,
            bootstrap_features=self.bootstrap_features,
            # oob_score=... XXX may be added if selection on tree perf needed.
            # warm_start=... XXX may be added to increase computation perf.
            n_jobs=self.n_jobs,
            random_state=self.random_state,
            verbose=self.verbose)

        bagging_reg = BaggingRegressor(
            base_estimator=DecisionTreeRegressor(
                max_depth=self.max_depth,
                max_features=self.max_features,
                min_samples_split=self.min_samples_split),
            n_estimators=self.n_estimators,
            max_samples=self.max_samples_,
            max_features=self.max_samples_features,
            bootstrap=self.bootstrap,
            bootstrap_features=self.bootstrap_features,
            # oob_score=... XXX may be added if selection on tree perf needed.
            # warm_start=... XXX may be added to increase computation perf.
            n_jobs=self.n_jobs,
            random_state=self.random_state,
            verbose=self.verbose)

        bagging_clf.fit(X, y)
        y_reg = y  # XXX todo define y_reg
        bagging_reg.fit(X, y_reg)

        self.estimators_ += bagging_clf.estimators_
        self.estimators_ += bagging_reg.estimators_

        self.estimators_samples_ += bagging_clf.estimators_samples_
        self.estimators_samples_ += bagging_reg.estimators_samples_

        self.estimators_features_ += bagging_clf.estimators_features_
        self.estimators_features_ += bagging_reg.estimators_features_

        rules_ = []
        for estimator, samples, features in zip(self.estimators_,
                                                self.estimators_samples_,
                                                self.estimators_features_):

            # Create mask for OOB samples
            mask = ~samples
            if sum(mask) == 0:
                warn("OOB evaluation not possible: doing it in-bag")
                mask = samples
            rules_from_tree = self._tree_to_rules(
                estimator, np.array(self.feature_names_)[features])

            # XXX todo: idem without dataframe
            X_oob = pandas.DataFrame((X[mask, :])[:, features],
                                     columns=np.array(
                                         self.feature_names_)[features])
            y_oob = y[mask]
            y_oob = np.array((y_oob != 0))
            # Add OOB performances to rules:

            rules_from_tree = [(r, self._eval_rule_perf(r, X_oob, y_oob))
                               for r in set(rules_from_tree)]
            rules_ += rules_from_tree

        # keep only rules verifying precision_min and recall_min:
        for rule, score in rules_:
            if (score[0] > self.precision_min and score[1] > self.recall_min):
                if rule in self.rules_:
                    # update the score to the new mean
                    c = self.rules_[rule][2] + 1
                    b = self.rules_[rule][1] + 1. / c * (
                        score[1] - self.rules_[rule][1])
                    a = self.rules_[rule][0] + 1. / c * (
                        score[0] - self.rules_[rule][0])

                    self.rules_[rule] = (a, b, c)
                else:
                    self.rules_[rule] = (score[0], score[1], 1)

        self.rules_ = sorted(self.rules_.items(),
                             key=lambda x: (x[1][0], x[1][1]), reverse=True)
        return self

    def predict(self, X):
        """Predict if a particular sample is an outlier or not.

        Parameters
        ----------
        X : array-like, shape (n_samples, n_features)
            The input samples. Internally, it will be converted to
            ``dtype=np.float32`` XXX allow sparse matrix?

        Returns
        -------
        is_inlier : array, shape (n_samples,)
            For each observations, tells whether or not (+1 or -1) it should
            be considered as an inlier according to the fitted model.
        """

        return np.array((self.decision_function(X) > 0), dtype=int)

    def decision_function(self, X):
        """Average anomaly score of X of the base classifiers (rules).

        The anomaly score of an input sample is computed as
        the negative weighted sum of the binary rules outputs. The weight is
        the respective precision of each rule.

        Parameters
        ----------
        X : array-like, shape (n_samples, n_features)
            The training input samples.

        Returns
        -------
        scores : array, shape (n_samples,)
            The anomaly score of the input samples.
            The lower, the more abnormal. Negative scores represent outliers,
            null scores represent inliers.

        """
        # Check if fit had been called
        check_is_fitted(self, ['rules_', 'estimators_', 'estimators_samples_',
                               'max_samples_'])

        # Input validation
        X = check_array(X)

        if X.shape[1] != self.n_features_:
            raise ValueError("X.shape[1] = %d should be equal to %d, "
                             "the number of features at training time."
                             " Please reshape your data."
                             % (X.shape[1], self.n_features_))

        selected_rules = self.rules_[:self.n_estimators]
        df = pandas.DataFrame(X, columns=self.feature_names_)

        scores = np.zeros(X.shape[0])
        for (r, w) in selected_rules:
            scores[list(df.query(r).index)] += w[0]

        return scores

    def _tree_to_rules(self, tree, feature_names):
        """
        Return a list of rules from a tree

        Parameters
        ----------
            tree : Decision Tree Classifier/Regressor
            feature_names: list of variable names

        Returns
        -------
        rules : list of rules.
        """
        # XXX todo: check the case where tree is build on subset of features,
        # ie max_features != None

        tree_ = tree.tree_
        feature_name = [
            feature_names[i] if i != _tree.TREE_UNDEFINED else "undefined!"
            for i in tree_.feature
        ]
        rules = []

        def recurse(node, base_name):
            if tree_.feature[node] != _tree.TREE_UNDEFINED:
                name = feature_name[node]
                symbol = '<='
                symbol2 = '>'
                threshold = tree_.threshold[node]
                text = base_name + ["{} {} {}".format(name, symbol, threshold)]
                recurse(tree_.children_left[node], text)

                text = base_name + ["{} {} {}".format(name, symbol2,
                                                      threshold)]
                recurse(tree_.children_right[node], text)
            else:
                rule = str.join(' and ', base_name)
                rule = (rule if rule != ''
                        else '=='.join([feature_names[0]] * 2))
                # better than "c0==c0" for a rule selecting all?
                rules.append(rule)

        recurse(0, [])

        return rules if len(rules) > 0 else 'True'

    def _eval_rule_perf(self, rule, X, y):
        # import pdb; pdb.set_trace()
        detected_index = list(X.query(rule).index)
        if len(detected_index) <= 1:
            return (-1, -1)
        y_detected = y[detected_index]
        true_pos = y_detected[y_detected > 0].sum()
        if true_pos == 0:
            return (-1, -1)
        pos = y[y > 0].sum()
        return y_detected.mean(), float(true_pos) / pos


if __name__ == '__main__':
    rnd = np.random.RandomState(0)
    X = 3 * rnd.uniform(size=(50, 5)).astype(np.float32)
    y = np.array([1] * (X.shape[0] - 10) + [0] * 10)
    clf = FraudToRules()
    clf.fit(X, y)
    clf.predict(X)
