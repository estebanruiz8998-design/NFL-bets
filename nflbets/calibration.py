"""Tiny logistic-regression fitter (Newton-Raphson) so betting probabilities
are calibrated on historical outcomes instead of assumed from a Normal curve."""

from __future__ import annotations

import numpy as np


def sigmoid(z):
    z = np.clip(z, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-z))


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1e-4,
                 iters: int = 50, tol: float = 1e-10) -> np.ndarray:
    """Fit P(y=1) = sigmoid(X @ w). No intercept unless X contains a 1s column."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = sigmoid(X @ w)
        grad = X.T @ (p - y) + l2 * w
        W = p * (1.0 - p)
        H = (X * W[:, None]).T @ X + l2 * np.eye(X.shape[1])
        step = np.linalg.solve(H, grad)
        w -= step
        if float(np.abs(step).max()) < tol:
            break
    return w
