import pickle
import sys
from functools import partial
from glob import glob

import numpy as np
import pandas as pd
import scipy as sp
import torch
from scipy.stats import spearmanr
from tqdm import tqdm


class histogramBasedCoefInitializer:
    def __init__(self):
        self.bins = None

    def fit(self, labels):
        self.bins = pd.Series(
            labels).value_counts().sort_index().cumsum().values
        return self

    def predict(self, preds):
        preds = sorted(preds)
        res_threshs = []
        if self.bins is None:
            raise Exception('plz fit at first.')
        for _bin in self.bins[:-1]:
            res_threshs.append((preds[_bin - 1] + preds[_bin]) / 2)
        return res_threshs


class OptimizedRounder(object):
    """
    An optimizer for rounding thresholds
    to maximize Quadratic Weighted Kappa (QWK) score
    # https://www.kaggle.com/naveenasaithambi/optimizedrounder-improved
    """

    def __init__(self):
        self.coef_ = 0

    def _spearmanr_loss(self, coef, X, y, labels):
        """
        Get loss according to
        using current coefficients
        :param coef: A list of coefficients that will be used for rounding
        :param X: The raw predictions
        :param y: The ground truth labels
        """
        X_p = pd.cut(X, [-np.inf] + list(np.sort(coef)) +
                     [np.inf], labels=labels)

        # return -np.mean(spearmanr(y, X_p).correlation)
        return -spearmanr(y, X_p).correlation

    def fit(self, X, y, initial_coef):
        """
        Optimize rounding thresholds
        :param X: The raw predictions
        :param y: The ground truth labels
        """
        labels = self.labels
        loss_partial = partial(self._spearmanr_loss, X=X, y=y, labels=labels)
        self.coef_ = sp.optimize.minimize(
            loss_partial, initial_coef, method='nelder-mead')

    def predict(self, X, coef):
        """
        Make predictions with specified thresholds
        :param X: The raw predictions
        :param coef: A list of coefficients that will be used for rounding
        """
        labels = self.labels
        return pd.cut(X, [-np.inf] + list(np.sort(coef)) +
                      [np.inf], labels=labels)
        # [np.inf], labels=[0, 1, 2, 3])

    def coefficients(self):
        """
        Return the optimized coefficients
        """
        return self.coef_['x']

    def set_labels(self, labels):
        self.labels = labels


def compute_spearmanr(trues, preds):
    rhos = []
    for col_trues, col_pred in zip(trues.T, preds.T):
        if len(np.unique(col_pred)) == 1:
            if col_pred[0] == np.max(col_trues):
                col_pred[np.argmin(
                    col_pred)] = np.min(col_trues)
            else:
                col_pred[np.argmax(
                    col_pred)] = np.max(col_trues)
        rhos.append(
            spearmanr(
                col_trues,
                col_pred
                #                  + np.random.normal(
                #                     0,
                #                     1e-7,
                #                     col_pred.shape[0])
            ).correlation)
    return rhos


def get_best_ckpt(ckpts):
    ckpt_dicts = []
    for ckpt in ckpts:
        ckpt_dict = {}
        ckpt_dict['ckpt'] = ckpt
        splitted_ckpt = ckpt.split('/')[-1].split('_')
        ckpt_dict['val_metric'] = float(splitted_ckpt[5])
        ckpt_dicts.append(ckpt_dict)
    ckpt_df = pd.DataFrame(ckpt_dicts)
    return ckpt_df.sort_values('val_metric', ascending=False).ckpt.iloc[0]


def opt(BASE_PATH, num_labels=30):
    # BASE_PATH = './mnt/checkpoints/e030/'

    y_preds = []
    y_trues = []
    best_dict = {}
    for i in tqdm(list(range(5))):
        filename = get_best_ckpt(glob(f'{BASE_PATH}/{i}/*.pth'))
        ckpt = torch.load(filename)
        y_preds.append(ckpt['val_y_preds'])
        y_trues.append(ckpt['val_y_trues'])
        best_dict[i] = ckpt['model_state_dict']
    y_preds = np.concatenate(y_preds)
    y_trues = np.concatenate(y_trues)
    torch.save(best_dict, f'{BASE_PATH}/best_dict.pth')
    del best_dict

    reses = []
    optRs = []

    for i in tqdm(list(range(num_labels))):
        y_pred = y_preds[:, i]
        y_true = y_trues[:, i]

        y_pred_argmax = np.argmax(y_pred)
        y_pred_argmin = np.argmin(y_pred)

        optR = OptimizedRounder()
        labels = np.sort(np.unique(y_true))
        optR.set_labels(labels)
        initer = histogramBasedCoefInitializer().fit(y_true)
        initial_coef = initer.predict(y_pred)
        optR.fit(y_pred, y_true, initial_coef=initial_coef)
        optRs.append(optR)
        res = optR.predict(y_pred, optR.coefficients())

        if len(np.unique(res)) == 1:
            if np.unique(res) == res[y_pred_argmax]:
                res[y_pred_argmin] = np.min(y_true)
            else:
                res[y_pred_argmax] = np.max(y_true)

        reses.append(res)
    reses = np.asarray(reses).T

    with open(f'{BASE_PATH}/optRs.pkl', 'wb') as fout:
        pickle.dump(optRs, fout)

    original_score = compute_spearmanr(y_trues, y_preds)
    print(f'original_score: {original_score}')
    print(f'original_score: {np.mean(original_score)}')

    res_score = compute_spearmanr(y_trues, reses)
    print(f'res_score: {res_score}')
    print(f'res_score_mean: {np.mean(res_score)}')

    return res_score


if __name__ == '__main__':
    args = sys.argv
    base_path = args[1]
    if len(args) == 3:
        num_labels = int(args[2])
    opt(base_path, num_labels)
