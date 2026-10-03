"""A small stochastic source-use model, not a simulator of LLM cognition.

``transmission_probability`` controls selection of a cross-run source conditional
on available context and no same-run replay. It is not the realized theta. Truth
labels record the selected generative source; they do not assert that removing
that source would necessarily change an output that has redundant alternatives.
"""

import hashlib
import random
from collections import defaultdict
from dataclasses import replace

from .model import ContextEntry, Delivery, Request, SimulationConfig, World, Write


def _token(seed: int, name: str) -> str:
    return "w_" + hashlib.sha256(f"{seed}:{name}".encode()).hexdigest()[:16]


def simulate(config: SimulationConfig = SimulationConfig()) -> World:
    """Generate one fixed world for all observation-regime comparisons.

    Tasks share a page, a launch-wave center, and a scaffold concept. A small
    fraction of independently generated writes reuse scaffold-supplied witness
    strings: these are hidden common sources, not implausible hash collisions.
    Successful page responses can fail to enter context; context entries persist
    and can remain unused. Requests and deliveries exist even when p_tx is zero.
    """
    if not isinstance(config, SimulationConfig):
        raise TypeError("config must be a SimulationConfig")
    rng = random.Random(config.seed)
    schedule = []
    for run in range(config.n_runs):
        family = rng.randrange(config.n_task_families)
        # Increasing shock compresses start times around family-specific waves.
        start = ((1 - config.shock_strength) * rng.uniform(0, 200)
                 + config.shock_strength * (family * 25 + rng.uniform(0, 5)))
        for ordinal in range(config.writes_per_run):
            timestamp = start + ordinal * 5 + rng.uniform(0, 1)
            schedule.append((timestamp, run, ordinal, family))
    schedule.sort()

    writes = []
    requests = []
    deliveries = []
    contexts = []
    truth_edges = set()
    by_page = defaultdict(list)
    by_run = defaultdict(list)
    available_context = defaultdict(dict)
    handles = {}

    for index, (timestamp, run, ordinal, family) in enumerate(schedule):
        event_id = f"e{index:06d}"
        run_id = f"r{run:05d}"
        page = f"task-{family}"
        if run_id not in handles or rng.random() < config.handle_rotation_probability:
            # Handle generation is independent of stable identity and event order.
            handles[run_id] = "h_" + rng.getrandbits(64).to_bytes(8, "big").hex()

        # One request opportunity per write, aimed at a recent same-task source.
        cross_sources = [w for w in by_page[page] if w.run_id != run_id]
        if cross_sources and rng.random() < config.request_probability:
            source = rng.choice(cross_sources[-8:])
            gap = timestamp - source.timestamp
            request_id = f"q{len(requests):06d}"
            requests.append(Request(request_id, source.timestamp + gap * 0.25,
                                    run_id, page))
            if rng.random() < config.delivery_probability:
                deliveries.append(Delivery(request_id, source.timestamp + gap * 0.5,
                                           run_id, source.event_id))
                if rng.random() < config.context_probability:
                    contexts.append(ContextEntry(
                        request_id, source.timestamp + gap * 0.75, run_id,
                        source.event_id, source.concepts, source.witness_tokens,
                    ))
                    available_context[run_id][source.event_id] = source

        selected = None
        own_writes = by_run[run_id]
        if own_writes and rng.random() < config.same_run_reuse_probability:
            selected = rng.choice(own_writes)
        elif available_context[run_id] and rng.random() < config.transmission_probability:
            selected = rng.choice(list(available_context[run_id].values()))
            truth_edges.add((selected.event_id, event_id))

        witness_tokens = []
        if selected is not None:
            concepts = selected.concepts
            if rng.random() < config.witness_retention_probability:
                witness_tokens.extend(selected.witness_tokens)
        else:
            if rng.random() < 0.25 + 0.7 * config.shock_strength:
                concepts = (f"shared-task-concept-{family}",)
            else:
                concepts = ("local-concept-" + _token(config.seed, f"local-{run_id}"),)
        if rng.random() < config.witness_probability:
            witness_tokens.append(_token(config.seed, event_id))
        if rng.random() < config.shared_witness_probability:
            witness_tokens.append(_token(config.seed, f"scaffold-{family}"))
        write = Write(event_id, timestamp, page, handles[run_id], concepts,
                      tuple(sorted(set(witness_tokens))), run_id)
        writes.append(write)
        by_page[page].append(write)
        by_run[run_id].append(write)

    return World(
        config, tuple(writes), tuple(sorted(requests, key=lambda x: x.timestamp)),
        tuple(sorted(deliveries, key=lambda x: x.timestamp)),
        tuple(sorted(contexts, key=lambda x: x.timestamp)), frozenset(truth_edges),
        frozenset(w.event_id for w in writes),
    )


def observational_equivalence_pair() -> tuple[World, World]:
    """Return identical logs with distinct latent source-use mechanisms.

    In the first world the target emits a token from its shared scaffold while
    leaving an exposed source unused. In the second it selects the source that
    contains the same token. Even context-entry receipts are identical. This is
    a constructive ambiguity example, not a newly proved causal theorem.
    """
    config = SimulationConfig(n_runs=2, writes_per_run=1, n_task_families=1)
    source = Write("e000000", 0.0, "task-0", "handle-a", ("shared",), ("w_shared",), "r0")
    target = Write("e000001", 1.0, "task-0", "handle-b", ("shared",), ("w_shared",), "r1")
    world = World(
        config, (source, target), (Request("q0", 0.25, "r1", "task-0"),),
        (Delivery("q0", 0.5, "r1", source.event_id),),
        (ContextEntry("q0", 0.75, "r1", source.event_id,
                      source.concepts, source.witness_tokens),),
        frozenset(), frozenset((source.event_id, target.event_id)),
    )
    return world, replace(world, truth_edges=frozenset(((source.event_id, target.event_id),)))
