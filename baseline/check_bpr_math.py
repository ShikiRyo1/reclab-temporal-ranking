"""Numerical gradient check for the BPR objective; independent of notebook prose.

Cornac v2.3.0 source inspected at:
https://github.com/PreferredAI/cornac/blob/v2.3.0/cornac/models/bpr/recom_bpr.pyx#L247-L266
The installed implementation uses ascent and NEGATIVE regularization terms.
This checks the equations for one fixed (user, positive item, negative item) triple;
it does not claim to verify every compiled Cornac execution path.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np

def objective(theta: np.ndarray, regularization: float) -> float:
    """log(sigmoid(score gap)) - (lambda/2) * squared parameter norm."""
    user, positive, negative = theta[:3], theta[3:6], theta[6:9]
    gap = user @ (positive - negative) + theta[9] - theta[10]
    return float(-np.logaddexp(0.0, -gap) - 0.5 * regularization * (theta @ theta))

def analytic_gradient(theta: np.ndarray, regularization: float) -> np.ndarray:
    user, positive, negative = theta[:3], theta[3:6], theta[6:9]
    gap = user @ (positive - negative) + theta[9] - theta[10]
    z = 1.0 / (1.0 + np.exp(gap))
    likelihood = np.r_[z * (positive - negative), z * user, -z * user, z, -z]
    return likelihood - regularization * theta

def main() -> None:
    # Fixed, nonzero parameters expose both score and regularization signs.
    theta = np.array([0.2, -0.3, 0.5, 0.4, 0.1, -0.2, -0.1, 0.2, 0.3, 0.05, -0.02], dtype=np.float64)
    regularization, epsilon, learning_rate = 0.1, 1e-6, 0.01
    analytical = analytic_gradient(theta, regularization)
    numerical = np.zeros_like(theta)
    for index in range(len(theta)):
        plus, minus = theta.copy(), theta.copy()
        plus[index] += epsilon
        minus[index] -= epsilon
        numerical[index] = (objective(plus, regularization) - objective(minus, regularization)) / (2 * epsilon)
    error = float(np.max(np.abs(analytical - numerical)))
    before = objective(theta, regularization)
    after = objective(theta + learning_rate * analytical, regularization)
    norm_before = float(np.linalg.norm(theta))
    norm_shrink = float(np.linalg.norm(theta - learning_rate * regularization * theta))
    norm_wrong = float(np.linalg.norm(theta + learning_rate * regularization * theta))
    assert error < 1e-7, f"Finite-difference check failed: {error}"
    assert after > before, "Small ascent step should improve this fixed objective"
    assert norm_shrink < norm_before < norm_wrong, "Regularization sign check failed"
    result = {
        "status": "PASS", "regularization_convention": "J=log(sigmoid(gap))-(lambda/2)*||theta||^2",
        "theta": theta.tolist(), "lambda": regularization, "epsilon": epsilon,
        "analytical_gradient": analytical.tolist(), "finite_difference_gradient": numerical.tolist(),
        "max_absolute_gradient_error": error, "objective_before": before, "objective_after_ascent": after,
        "parameter_norm_before": norm_before, "norm_after_regularization_only": norm_shrink,
        "norm_after_wrong_positive_regularization": norm_wrong,
        "d_log_sigmoid_at_x_1": float(1.0 / (1.0 + np.exp(1.0))),
        "cornac_source": "https://github.com/PreferredAI/cornac/blob/v2.3.0/cornac/models/bpr/recom_bpr.pyx#L247-L266",
        "conclusion": "Notebook prose has sign errors; inspected Cornac 2.3.0 update has positive likelihood and negative regularization gradients.",
        "scope": "Numerical check of the mathematical update for one triple; not an exhaustive test of compiled Cornac."
    }
    destination = Path(__file__).resolve().parents[1] / "reports" / "baseline" / "bpr_gradient_check.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
