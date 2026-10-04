"""Derive target errors from unchanged original per-world rows, without simulation."""

import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import fmean

ROOT = Path(__file__).resolve().parents[2]
METRICS = ("false_positive_target_fraction", "false_negative_target_fraction",
           "signed_error", "absolute_error", "target_disagreement")


def derive_row(row):
    n = int(row["eligible_targets"])
    if n <= 0:
        raise ValueError("Nonpositive eligible denominator")
    theta, theta_hat = float(row["theta"]), float(row["theta_hat"])
    fp = float(row["false_attributed_target_fraction"])
    signed = theta_hat - theta
    fn = fp - signed
    disagreement = fp + fn
    values = (theta, theta_hat, fp, fn, disagreement)
    if not all(math.isfinite(x) and -1e-12 <= x <= 1 + 1e-12 for x in values):
        raise ValueError("Target fraction outside [0,1]")
    if fp > 1 - theta + 1e-12 or fn > theta + 1e-12:
        raise ValueError("FP/FN incompatible with true target prevalence")
    for value in (theta, theta_hat, fp, fn):
        if not math.isclose(value * n, round(value * n), abs_tol=1e-10):
            raise ValueError("Fraction incompatible with integer target counts")
    if not math.isclose(abs(signed), float(row["absolute_error"]), abs_tol=1e-12):
        raise ValueError("Saved absolute error disagrees")
    fp_count, fn_count = round(fp * n), round(fn * n)
    if not math.isclose(signed, (fp_count - fn_count) / n, abs_tol=1e-12):
        raise ValueError("Signed target-error identity failed")
    return {"seed": int(row["seed"]), "transmission_probability": 0.3,
            "shock_strength": 0.9, "method": "witness", "regime": row["regime"],
            "eligible_targets": n, "theta": theta, "theta_hat": theta_hat,
            "false_positive_targets": fp_count, "false_negative_targets": fn_count,
            "false_positive_target_fraction": fp, "false_negative_target_fraction": fn,
            "signed_error": signed, "absolute_error": abs(signed),
            "target_disagreement": disagreement}


def derive(rows):
    selected = [derive_row(r) for r in rows
                if float(r["transmission_probability"]) == 0.3
                and float(r["shock_strength"]) == 0.9 and r["method"] == "witness"
                and r["regime"] in ("requests", "context")]
    groups = {regime: [r for r in selected if r["regime"] == regime]
              for regime in ("requests", "context")}
    for rows in groups.values():
        if len(rows) != 12 or sorted(r["seed"] for r in rows) != list(range(12)):
            raise ValueError("Require exactly the original paired seeds 0–11")
        if {r["eligible_targets"] for r in rows} != {360}:
            raise ValueError("Original scenario requires 360 eligible writes")
    paired = []
    for seed in range(12):
        a, b = (next(r for r in groups[g] if r["seed"] == seed)
                for g in ("requests", "context"))
        if a["theta"] != b["theta"]:
            raise ValueError("Paired rows disagree on world truth")
        paired.append({"seed": seed, **{m: b[m] - a[m] for m in METRICS}})
    means = {g: {m: fmean(r[m] for r in rows) for m in METRICS}
             for g, rows in groups.items()}
    paired_means = {m: fmean(r[m] for r in paired) for m in METRICS}
    return {"scenario": {"transmission_probability": 0.3, "shock_strength": 0.9,
                         "method": "witness", "seeds": list(range(12)),
                         "eligible_targets_per_world": 360},
            "derivation": "FN/N = FP/N - (theta_hat-theta); disagreement = FP/N + FN/N. "
                          "Means average per-world absolute errors, never absolute mean signed error.",
            "rows": sorted(selected, key=lambda r: (r["seed"], r["regime"])),
            "means": means, "paired_context_minus_requests": paired,
            "paired_mean_context_minus_requests": paired_means,
            "identity_and_count_checks_passed": True,
            "estimand": "Direct realized cross-run structural source-selection target fraction; "
                         "not a measured wiki copying rate.",
            "limitations": "Derived historical results are conditional on the legacy simulator, "
                           "including the chronology limitation audited separately. No corrected "
                           "simulation or changed historical score was computed."}


def main():
    path = ROOT / "results/runs.csv"
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = json.loads((ROOT / "results/manifest.json").read_text())
    if sha != manifest["files"]["runs.csv"]:
        raise ValueError("Original result rows no longer match historical manifest")
    with path.open(newline="") as handle:
        output = derive(list(csv.DictReader(handle)))
    output["inputs"] = {"results/runs.csv": sha,
                        "results/manifest.json": hashlib.sha256(
                            (ROOT / "results/manifest.json").read_bytes()).hexdigest()}
    directory = Path(__file__).resolve().parent
    with (directory / "derived_target_errors.json").open("x") as handle:
        json.dump(output, handle, indent=2, sort_keys=True)
        handle.write("\n")
    with (directory / "derived_target_errors.csv").open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output["rows"][0]))
        writer.writeheader()
        writer.writerows(output["rows"])
    print(json.dumps({"means": output["means"], "paired_means":
                      output["paired_mean_context_minus_requests"]}, indent=2))


if __name__ == "__main__":
    main()
