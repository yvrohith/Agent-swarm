"""Same-proposal support over every physical member of the fixed M2 closure.

Complete observable signatures partition physical realizations. A paid-history
signature mask therefore selects whole cells, including every opposite-truth
witness within a mixed cell. Census rewards count signatures, never worlds.
"""
from __future__ import annotations

import copy

from studies.audit_aware_acquisition.auditing import _history, _signature
from tracebench.evidence_acquisition.model import indices, pin

DEFINITE = {"established", "ruled_out"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


class SupportContract:
    """Hypothetical physical semantics, with no realized archive or actual k."""

    def __init__(self, nominal, expanded2, base_history, proposal):
        require(expanded2.k == 2, "Planning support requires the fixed hypothetical M2 closure")
        require(expanded2.nominal.model_pin == nominal.model_pin,
                "Physical support and nominal model pins disagree")
        require(tuple(expanded2.query_ids) == tuple(nominal.query_ids),
                "Physical support and nominal catalogue orders disagree")
        self.nominal, self.expanded = nominal, expanded2
        self.base_history = copy.deepcopy(_history(nominal, base_history))
        nominal_state = nominal.compatible(self.base_history)
        require(bool(nominal_state) and proposal in {*DEFINITE, "archive_irreducible"}
                and nominal.terminal(nominal_state) == proposal,
                "Support contract requires the original consistent nominal proposal")
        self.proposal = proposal
        self.design_signatures = tuple(sorted(expanded2.signature_cells))
        require(0 < len(self.design_signatures) <= 256, "Invalid bounded physical signature envelope")
        for signature in self.design_signatures:
            _signature(nominal, signature)
        require(set(nominal.signature_cells) <= set(self.design_signatures),
                "Physical envelope omits original nominal signatures")
        self.full_mask = (1 << len(self.design_signatures)) - 1
        self.original_signature_mask = sum(1 << i for i, signature in enumerate(self.design_signatures)
                                           if signature in nominal.signature_cells)
        self._positions = {qid: index for index, qid in enumerate(nominal.query_ids)}
        self._cells = tuple(expanded2.signature_cells[signature] for signature in self.design_signatures)
        require(all(type(cell) is int and cell > 0 for cell in self._cells),
                "A physical signature cell must be nonempty")
        require(sum(cell.bit_count() for cell in self._cells) == len(expanded2.worlds)
                and sum(self._cells) == (1 << len(expanded2.worlds)) - 1,
                "Signature cells do not partition all physical realizations")
        self._truth = tuple(frozenset(expanded2.claim_values[i] for i in indices(cell))
                            for cell in self._cells)
        require(all(values and values <= {False, True} for values in self._truth),
                "Physical claim truth must be total and Boolean")
        self.root_mask = self._filter(self.base_history)
        require(bool(self.root_mask), "Original paid history has empty physical support")
        self.physical_pin = pin({"expanded_model_pin": expanded2.model_pin,
                                 "expanded_contract_pin": expanded2.contract_pin,
                                 "expanded_support_pin": expanded2.support_pin,
                                 "claim": expanded2.claim})

    def _filter(self, history):
        return sum(1 << i for i, signature in enumerate(self.design_signatures)
                   if all(signature[self._positions[row["query_id"]]] == row["outcome_id"]
                          for row in history))

    def _mask(self, mask):
        require(type(mask) is int and mask > 0 and not mask & ~self.root_mask,
                "Support requires a nonempty root-compatible physical signature mask")
        return tuple(indices(mask))

    def mask(self, history):
        history = _history(self.nominal, history)
        require(history[:len(self.base_history)] == self.base_history,
                "Paid history does not extend this ordered H0")
        mask = self._filter(history)
        self._mask(mask)
        return mask

    def supported(self, mask):
        positions = self._mask(mask)
        return self.proposal in DEFINITE and all(
            self._truth[i] == {self.proposal == "established"} for i in positions)

    def attainable(self, mask):
        """Existential full-cell continuation; this is not irreducibility."""
        positions = self._mask(mask)
        return self.proposal in DEFINITE and any(
            self._truth[i] == {self.proposal == "established"} for i in positions)

    def reward(self, mask):
        return (mask & self.original_signature_mask).bit_count() if self.supported(mask) else 0

    def assess(self, history):
        mask = self.mask(history)
        positions = self._mask(mask)
        values = set().union(*(self._truth[i] for i in positions))
        claim = "unresolved" if len(values) == 2 else "established" if True in values else "ruled_out"
        terminal = claim
        if claim == "unresolved":
            terminal = "archive_irreducible" if all(len(self._truth[i]) == 2 for i in positions) else "unresolved_pending"
        return {"claim_status": claim, "terminal_status": terminal,
                "supported": self.supported(mask), "attainable": self.attainable(mask),
                "reward": self.reward(mask), "compatible_signature_count": mask.bit_count(),
                "compatible_original_signature_count": (mask & self.original_signature_mask).bit_count(),
                "compatible_physical_world_count": sum(self._cells[i].bit_count() for i in positions),
                "nominal_conflict": not bool(self.nominal.compatible(history))}
