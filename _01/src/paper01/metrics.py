from __future__ import annotations

import numpy as np


def eq5_mre(prediction: np.ndarray, target: np.ndarray) -> float:
    prediction = np.asarray(prediction)
    target = np.asarray(target)
    denominator = np.abs(target)
    values = np.where(denominator != 0, np.abs(prediction - target) / np.where(denominator != 0, denominator, 1), np.abs(prediction))
    return float(np.mean(values))


def nmae(prediction: np.ndarray, target: np.ndarray) -> float:
    denominator = float(np.max(np.abs(target)))
    return float(np.mean(np.abs(prediction - target)) / max(denominator, 1e-30))


def rel_l2(prediction: np.ndarray, target: np.ndarray) -> float:
    return float(np.linalg.norm(prediction - target) / max(float(np.linalg.norm(target)), 1e-30))


def summarize(prediction: np.ndarray, target: np.ndarray) -> dict:
    rows = []
    for i in range(len(target)):
        components = []
        for c in range(3):
            components.append({
                "nmae": nmae(prediction[i, c], target[i, c]),
                "rel_l2": rel_l2(prediction[i, c], target[i, c]),
                "mre_eq5": eq5_mre(prediction[i, c], target[i, c]),
            })
        rows.append({
            "macro_nmae": float(np.mean([row["nmae"] for row in components])),
            "global_rel_l2": rel_l2(prediction[i], target[i]),
            "macro_mre_eq5": float(np.mean([row["mre_eq5"] for row in components])),
            "components": components,
        })
    return {
        "samples": len(rows),
        "macro_nmae_mean": float(np.mean([row["macro_nmae"] for row in rows])),
        "global_rel_l2_p90": float(np.percentile([row["global_rel_l2"] for row in rows], 90)),
        "macro_mre_eq5_mean": float(np.mean([row["macro_mre_eq5"] for row in rows])),
        "individual": rows,
    }
