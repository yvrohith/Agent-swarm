"""Certified receipt triplets using the unchanged utility finite-world oracle.

Family names and transformations are evaluator metadata. Only each variant's
actual records, assumptions, primary query and opaque case ID enter its request.
"""

from __future__ import annotations

from copy import deepcopy

from tracebench.investigator_utility import synthetic_cases as oracle

from .common import ROLES, SALT, digest, opaque

MOTIFS = (
    "downstream_receipt_presence",
    "completeness_recipient_scope",
    "receipt_recipient_identity",
    "completeness_time_scope",
)
PUBLIC_FIELDS = ("case_id", "records", "assumptions", "claims")


def _settings(case: dict) -> dict:
    matches = [row["parameters"] for row in case["assumptions"]
               if row.get("parameters", {}).get("contract") == oracle.CONTRACT]
    if len(matches) != 1:
        raise ValueError("Expected one finite receipt contract")
    return matches[0]


def _oracle_case(case: dict) -> dict:
    """Restore query descriptions only; leave evidence and assumptions untouched.

    The historical oracle validates a four-query schema before enumeration. Its
    enumerator uses no query text/selection when constructing compatible worlds.
    This adapter verifies the actual public primary claim, then supplies that
    historical query template without adding any constraint, record or assumption.
    """
    if case.get("schema_version") != 1 or case.get("subset") != "receipt":
        raise ValueError("Expected a receipt responsiveness case")
    scope = _settings(case)["target_scope"]
    if case["claims"] != [{"id": "q0", "text": oracle._claim_text(scope, "context")}]:
        raise ValueError("The primary query must ask context entry for the declared target")
    adapted = deepcopy(case)
    adapted["subset"] = "synthetic"
    adapted["claims"] = [{"id": f"c{i:02}", "text": oracle._claim_text(scope, stage)}
                         for i, stage in enumerate(oracle.STAGES, 1)]
    return adapted


def certify_receipt(case: dict) -> dict:
    """Exhaust the actual variant, retaining rendered disagreeing constructions."""
    adapted = _oracle_case(case)
    result = oracle._gold(adapted)
    primary = deepcopy(result["claims"][2])
    primary["id"] = "q0"
    validation = deepcopy(result["validation"])
    validation["oracle_case_sha256"] = validation.pop("public_case_sha256")
    validation["public_case_sha256"] = digest({key: case[key] for key in PUBLIC_FIELDS})
    validation["adapter"] = (
        "Restore four canonical query descriptions and the private synthetic schema tag; "
        "records and assumptions are byte-identical under canonical serialization."
    )
    return {"case_id": case["case_id"], "claims": [primary], "validation": validation}


def _complete(scope: dict, record_id: str) -> dict:
    return {"id": record_id, "text": oracle._completeness_text("context", scope),
            "parameters": {"type": "complete_logging", "channel": "context", **scope}}


def _instance(split: str, motif: str, instance: int) -> dict:
    token = digest([SALT, "receipt-instance", split, motif, instance])[:10]
    # Similar-looking identifiers are distinct declared scopes, never motif names.
    source_id, run_id = f"s_{token}_0", f"r_{token}_0"
    start = 100 + 100 * (MOTIFS.index(motif) * 2 + instance + (20 if split == "development" else 0))
    scope = {"source_id": source_id, "run_id": run_id, "window": [start, start + 10]}
    decoys = [{**deepcopy(scope), "run_id": f"r_{token}_1"},
              {**deepcopy(scope), "source_id": f"s_{token}_1"}]
    topic = f"dispatch {token}"
    records = [
        {"id": "r01", "kind": "source_write", "source_id": source_id,
         "timestamp": start + 1, "body": f"Plan: {topic}"},
        {"id": "r02", "kind": "shared_input", "run_id": run_id,
         "timestamp": start + 1, "scaffold": "Plan: {topic}", "topic": topic},
        {"id": "r03", "kind": "target_write", "run_id": run_id,
         "timestamp": start + 9, "body": f"Result: Plan: {topic}."},
        *[{"id": f"r0{i + 4}", "kind": "request", **deepcopy(decoy),
           "timestamp": start + 2} for i, decoy in enumerate(decoys)],
    ]
    assumptions = [
        {"id": "a01", "text": oracle.FINITE_CONTRACT_TEXT,
         "parameters": {"contract": oracle.CONTRACT, "target_scope": deepcopy(scope),
                        "scopes": [deepcopy(scope), *deepcopy(decoys)],
                        "source_record_id": "r01", "shared_record_id": "r02",
                        "target_record_id": "r03"}},
        {"id": "a02", "text": oracle.AUTHENTICITY_TEXT},
        {"id": "a03", "text": oracle.LOGGING_TEXT},
    ]
    family_id = opaque("receipt-family", split, motif, instance)
    return {"schema_version": 1, "case_id": "", "subset": "receipt", "split": split,
            "cluster_id": family_id, "records": records, "assumptions": assumptions,
            "claims": [{"id": "q0", "text": oracle._claim_text(scope, "context")}]}


def _with_evidence(case: dict, motif: str, decisive_fact: bool) -> dict:
    """Materialize one state of the specified logical evidence edit."""
    case = deepcopy(case)
    settings = _settings(case)
    target, other = settings["scopes"][:2]
    if motif == "downstream_receipt_presence":
        if decisive_fact:
            case["records"].append({"id": "r06", "kind": "context", **deepcopy(target),
                                    "timestamp": target["window"][0] + 4})
    elif motif == "completeness_recipient_scope":
        case["assumptions"].append(_complete(deepcopy(target if decisive_fact else other), "a04"))
    elif motif == "receipt_recipient_identity":
        recipient = target if decisive_fact else other
        case["records"].append({"id": "r06", "kind": "context", **deepcopy(recipient),
                                "timestamp": recipient["window"][0] + 4})
    elif motif == "completeness_time_scope":
        declaration = deepcopy(target)
        declaration["window"][1] = target["window"][0] + (4 if decisive_fact else 3)
        case["assumptions"].append(_complete(declaration, "a04"))
    else:
        raise ValueError("Unknown fixed receipt motif")
    return case


def _nuisance(case: dict, instance: int) -> tuple[dict, dict]:
    case = deepcopy(case)
    if instance % 2 == 0:
        prior_order = [row["id"] for row in case["records"]]
        case["records"].reverse()
        return case, {"semantic_change": "Reverse record list order; explicit timestamps unchanged.",
                      "mechanical_updates": [], "prior_order": prior_order,
                      "presented_order": [row["id"] for row in case["records"]]}
    scopes = _settings(case)["scopes"]
    identifiers = sorted({scope[field] for scope in scopes for field in ("source_id", "run_id")})
    replacements = {value: "i_" + digest([SALT, "identifier-bijection", value])[:16]
                    for value in identifiers}

    def replace(value):
        if isinstance(value, dict):
            return {key: replace(child) for key, child in value.items()}
        if isinstance(value, list):
            return [replace(child) for child in value]
        if isinstance(value, str):
            for original, renamed in replacements.items():
                value = value.replace(original, renamed)
        return value

    case = replace(case)
    return case, {"semantic_change": "Consistent bijection of opaque source/run identifiers.",
                  "mechanical_updates": ["References, declarations and primary query renamed consistently."],
                  "identifier_bijection": replacements}


def _family(split: str, motif: str, instance: int) -> tuple[list[dict], list[dict], dict]:
    scaffold = _instance(split, motif, instance)
    base = _with_evidence(scaffold, motif, instance % 2 == 0)
    irrelevant, nuisance = _nuisance(base, instance)
    decisive = _with_evidence(scaffold, motif, instance % 2 != 0)
    cases = [base, irrelevant, decisive]
    for role, case in zip(ROLES, cases, strict=True):
        case["case_id"] = opaque("receipt-case", split, motif, instance, role)
    labels = [certify_receipt(case) for case in cases]
    statuses = [gold["claims"][0]["status"] for gold in labels]
    if statuses[0] != statuses[1] or statuses[0] == statuses[2]:
        raise ValueError("Receipt triplet does not satisfy its certified relationship")
    changes = {
        "downstream_receipt_presence": "Add/remove only the target context-entry receipt.",
        "completeness_recipient_scope": "Change only the completeness declaration's recipient run.",
        "receipt_recipient_identity": "Change only the context-entry receipt's recipient run.",
        "completeness_time_scope": "Change only completeness interval's upper bound across the event time.",
    }
    family = {"family_id": scaffold["cluster_id"], "subset": "receipt", "split": split,
              "cluster_id": scaffold["cluster_id"], "motif": motif,
              "variants": {role: case["case_id"] for role, case in zip(ROLES, cases, strict=True)},
              "transformations": {"irrelevant": nuisance, "decisive": {
                  "semantic_change": changes[motif],
                  "mechanical_updates": (["Completeness prose regenerated from the changed parameters."]
                                         if motif.startswith("completeness") else []),
                  "base_fact_present_or_relevant": instance % 2 == 0}},
              "provenance": {"generator": "fixed-receipt-triplets-v1", "salt": SALT,
                             "instance": instance, "oracle_contract": oracle.CONTRACT,
                             "oracle_rule": oracle.RULE, "declared_scopes": 3,
                             "decoy_scopes": 2,
                             "base_evidence_sha256": digest({key: base[key] for key in PUBLIC_FIELDS})}}
    return cases, labels, family


def build_receipt_families() -> dict:
    """Return eight evaluation triplets and one disjoint development triplet."""
    designs = [("development", MOTIFS[0], 2)] + [
        ("evaluation", motif, instance) for motif in MOTIFS for instance in (0, 1)]
    cases, gold, families = [], [], []
    for split, motif, instance in designs:
        variants, certificates, family = _family(split, motif, instance)
        cases.extend(variants)
        gold.extend(certificates)
        families.append(family)
    return {"cases": cases, "gold": gold, "families": families, "selection": {
        "schema_version": 1, "subset": "receipt", "salt": SALT,
        "rule": "Four fixed motifs; two independent reverse directions each; separate development instance.",
        "evaluation_families": 8, "development_families": 1, "variants_per_family": 3,
        "decoy_scopes_per_variant": 2, "oracle_scope_bound": 4,
        "no_model_outcome_selection": True, "rejected_candidates": [],
        "cases_sha256": digest(cases), "gold_sha256": digest(gold),
        "families_sha256": digest(families)}}
