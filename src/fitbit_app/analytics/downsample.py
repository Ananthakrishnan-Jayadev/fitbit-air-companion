"""Largest-Triangle-Three-Buckets downsampling for charts (keeps peaks and dips)."""

from __future__ import annotations

import numpy as np


def lttb_indices(x: np.ndarray, y: np.ndarray, threshold: int) -> np.ndarray:
    """Indices of at most `threshold` points that preserve the series' visual shape.

    `x` must be increasing. Always keeps the first and last point.
    """
    n = len(x)
    if threshold >= n or threshold < 3:
        return np.arange(n)

    x = x.astype(float)
    y = y.astype(float)
    selected = np.empty(threshold, dtype=int)
    selected[0] = 0
    selected[-1] = n - 1
    bucket_size = (n - 2) / (threshold - 2)
    previous = 0
    for i in range(threshold - 2):
        start = int(np.floor(i * bucket_size)) + 1
        end = int(np.floor((i + 1) * bucket_size)) + 1
        next_start = end
        next_end = min(int(np.floor((i + 2) * bucket_size)) + 1, n)
        # Average of the next bucket (or the last point for the final bucket).
        if next_start < next_end:
            avg_x = x[next_start:next_end].mean()
            avg_y = y[next_start:next_end].mean()
        else:
            avg_x, avg_y = x[-1], y[-1]
        bucket_x, bucket_y = x[start:end], y[start:end]
        areas = np.abs(
            (x[previous] - avg_x) * (bucket_y - y[previous])
            - (x[previous] - bucket_x) * (avg_y - y[previous])
        )
        previous = start + int(np.argmax(areas))
        selected[i + 1] = previous
    return selected
