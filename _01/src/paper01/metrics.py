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


def summarize(prediction: np.ndarray, target: np.ndarray,
              scales: np.ndarray | None = None) -> dict:
    """Per-sample metrics on the component-normalised targets.

    F09: ``global_rel_l2`` here is computed AFTER each component was divided
    by its own local maximum, so it re-weights the three components.  It is
    NOT the physical three-component relative L2 that ``phase1_full_run``
    reports under the same name -- the same physical prediction can read
    0.009999 one way and 0.57735 the other.  Both readings are returned under
    names that say which one they are, and the physical reading is only
    available when the caller passes the component ``scales`` that the
    normalisation removed.

    ``scales`` has shape (samples, 3) and holds each component's own local
    maximum.  Note that those maxima come from the TARGET, so the physical
    reading is a diagnostic: it is not a restoration rule the network could
    apply from its input alone (F11).
    """
    rows = []
    for i in range(len(target)):
        components = []
        for c in range(3):
            components.append({
                "nmae": nmae(prediction[i, c], target[i, c]),
                "rel_l2": rel_l2(prediction[i, c], target[i, c]),
                "mre_eq5": eq5_mre(prediction[i, c], target[i, c]),
            })
        row = {
            "macro_nmae": float(np.mean([row["nmae"] for row in components])),
            # Kept under the historical key so existing tables stay readable.
            "global_rel_l2": rel_l2(prediction[i], target[i]),
            "component_normalized_vector_rel_l2": rel_l2(prediction[i], target[i]),
            "macro_mre_eq5": float(np.mean([row["mre_eq5"] for row in components])),
            "components": components,
        }
        if scales is not None:
            scale = np.asarray(scales[i], dtype=np.float64).reshape(3, 1, 1, 1)
            row["physical_vector_rel_l2"] = rel_l2(prediction[i] * scale, target[i] * scale)
        rows.append(row)
    physical = [row["physical_vector_rel_l2"] for row in rows if "physical_vector_rel_l2" in row]
    summary = {
        "samples": len(rows),
        "macro_nmae_mean": float(np.mean([row["macro_nmae"] for row in rows])),
        "global_rel_l2_p90": float(np.percentile([row["global_rel_l2"] for row in rows], 90)),
        "component_normalized_vector_rel_l2_p90": float(
            np.percentile([row["component_normalized_vector_rel_l2"] for row in rows], 90)),
        "macro_mre_eq5_mean": float(np.mean([row["macro_mre_eq5"] for row in rows])),
        "metric_contract": {
            "global_rel_l2": "component-normalised vector relative L2; NOT the "
                             "physical three-component relL2 used elsewhere",
            "physical_vector_rel_l2": "target-scale restored relative L2; the scale "
                                      "comes from the target, so it is diagnostic only",
            "nmae": "MAE/max on the component-normalised target",
        },
        "individual": rows,
    }
    if physical:
        summary["physical_vector_rel_l2_p90"] = float(np.percentile(physical, 90))
        summary["physical_vector_rel_l2_mean"] = float(np.mean(physical))
    return summary
