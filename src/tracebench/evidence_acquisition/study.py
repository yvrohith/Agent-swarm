"""Bounded offline study driver. Refuses to overwrite prepared/frozen results."""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from time import perf_counter

from .model import Model, pin
from .policies import ChargedLookup, Planner, budget_for, hindsight_minimum, run_policy

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / 'studies/evidence_acquisition'
STATES = ('established', 'ruled_out', 'archive_irreducible', 'unresolved_pending',
          'budget_exhausted_unresolved', 'inconsistent')


def read(path):
    def unique(pairs):
        value = {}
        for k, v in pairs:
            if k in value:
                raise ValueError('Duplicate JSON key')
            value[k] = v
        return value
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def number(value):
    return {'exact': str(value), 'value': float(value)}


def evaluate(problems, config):
    """Exact expectations over signatures; no hidden-world sampling or model calls."""
    rows, runs, certificates, runtime = [], [], {}, []
    total_queries = 0
    for problem in problems:
        started = perf_counter()
        model = Model(problem)
        preprocessing = perf_counter() - started
        planners = {name: Planner(model, name) for name in config['policies']}
        accumulator = {}
        started = perf_counter()
        hindsight = {}
        for signature, cell in sorted(model.signature_cells.items()):
            history = [{'query_id': q, 'outcome_id': o}
                       for q, o in zip(model.query_ids, signature, strict=True)]
            hindsight[signature] = hindsight_minimum(model, history)
            if not hindsight[signature]['certificate_valid']:
                raise ValueError('Invalid hindsight certificate')
        hindsight_seconds = perf_counter() - started
        signatures = sorted(model.signature_cells)
        for policy in config['policies']:
            for percent in config['budget_percentages']:
                metrics = {key: Fraction() for key in
                           ('cost', 'query_count', 'returned_bytes', 'hindsight_cost',
                            'certificate_failures', 'false_irreducibility', *STATES)}
                maxima = {key: 0 for key in ('cost', 'query_count', 'returned_bytes')}
                for signature_index, signature in enumerate(signatures):
                    mass = model.mass(model.signature_cells[signature])
                    result = run_policy(model, policy, ChargedLookup(model, signature),
                                        budget_for(model, percent), planner=planners[policy])
                    total_queries += result['query_count']
                    cert = result['certificate']
                    cert_id = pin(cert)
                    certificates.setdefault(cert_id, cert)
                    valid = model.verify_certificate(cert)
                    # Separately check each recorded lookup against the evaluator's retained signature.
                    actual_answers = dict(zip(model.query_ids, signature, strict=True))
                    actual = all(actual_answers[h['query_id']] == h['outcome_id']
                                 for h in result['history'])
                    if len({h['query_id'] for h in result['history']}) != result['query_count']:
                        raise ValueError('Repeated or uncharged query')
                    invalid = not (valid and actual and result['certificate_valid'])
                    terminal = model.terminal(model.signature_cells[signature])
                    false_irreducible = (result['status'] == 'archive_irreducible'
                                         and terminal != 'archive_irreducible')
                    if result['status'] not in STATES:
                        raise ValueError('Unknown result state')
                    for key in maxima:
                        metrics[key] += mass * result[key]
                        maxima[key] = max(maxima[key], result[key])
                    metrics[result['status']] += mass
                    metrics['hindsight_cost'] += mass * hindsight[signature]['cost']
                    metrics['certificate_failures'] += mass * invalid
                    metrics['false_irreducibility'] += mass * false_irreducible
                    hcert = hindsight[signature]['certificate']
                    hcert_id = pin(hcert)
                    certificates.setdefault(hcert_id, hcert)
                    runs.append({'problem_id': problem['problem_id'], 'policy': policy,
                                 'budget_percent': percent, 'signature_index': signature_index,
                                 'prior_mass': str(mass), 'status': result['status'],
                                 'certificate': cert_id, 'certificate_valid': not invalid,
                                 'cost': result['cost'], 'query_count': result['query_count'],
                                 'returned_bytes': result['returned_bytes'],
                                 'hindsight_cost': hindsight[signature]['cost'],
                                 'hindsight_certificate': hcert_id})
                if sum(metrics[s] for s in STATES) != 1:
                    raise ValueError('Outcome mass does not sum to one')
                row = {'problem_id': problem['problem_id'], 'seed': problem['seed'],
                       'stratum': problem['stratum'], 'subtype': problem['subtype'],
                       'policy': policy, 'budget_percent': percent,
                       'budget': budget_for(model, percent),
                       'read_all_cost': sum(q['cost'] for q in model.queries.values()),
                       'worlds': len(model.worlds), 'signatures': len(signatures),
                       'queries_available': len(model.queries),
                       'expected': {k: number(v) for k, v in metrics.items()},
                       'worst': maxima}
                rows.append(row)
                accumulator[policy, percent] = metrics
        optimum = planners['exact_optimal'].optimal_value()
        if accumulator['exact_optimal', 100]['cost'] != optimum:
            raise ValueError('Executed exact-policy expectation differs from DP')
        for policy in config['policies']:
            if accumulator[policy, 100]['cost'] < optimum:
                raise ValueError('Policy unexpectedly beats exact optimum')
            if accumulator[policy, 100]['hindsight_cost'] > optimum:
                raise ValueError('Hindsight cost exceeds adaptive optimum')
        runtime.append({'problem_id': problem['problem_id'],
                        'preprocessing_seconds': preprocessing,
                        'hindsight_seconds': hindsight_seconds,
                        'exact_value': str(optimum),
                        'planning_seconds': {k: p.planning_seconds for k, p in planners.items()},
                        'solver_states': planners['exact_optimal'].solver_states})
    return {'per_problem_policy_budget': rows, 'runs': runs, 'certificates': certificates,
            'runtime': runtime, 'charged_queries': total_queries}


def summarize(result):
    groups = defaultdict(list)
    for row in result['per_problem_policy_budget']:
        for level in ('stratum', 'subtype'):
            key = (level, row[level], row['policy'], row['budget_percent'])
            groups[key].append(row)
    summaries = []
    for (level, group, policy, budget), rows in sorted(groups.items()):
        keys = rows[0]['expected']
        summaries.append({'grouping': level, 'group': group, 'policy': policy,
                          'budget_percent': budget, 'problems': len(rows),
                          'mean_expected': {k: number(sum(
                              (Fraction(r['expected'][k]['exact']) for r in rows), Fraction())
                              / len(rows)) for k in keys}})
    full = [r for r in result['per_problem_policy_budget'] if r['budget_percent'] == 100]
    by_problem = defaultdict(dict)
    for r in full:
        by_problem[r['problem_id']][r['policy']] = r
    contrasts, ratios = [], []
    for pid, policies in sorted(by_problem.items()):
        proposed = policies['pair_cut']
        pcost = Fraction(proposed['expected']['cost']['exact'])
        optimal = Fraction(policies['exact_optimal']['expected']['cost']['exact'])
        for comparison in ('schema_aware', 'world_entropy', 'exact_optimal', 'read_all'):
            difference = pcost - Fraction(policies[comparison]['expected']['cost']['exact'])
            contrasts.append({'problem_id': pid, 'stratum': proposed['stratum'],
                              'subtype': proposed['subtype'], 'comparison': comparison,
                              'pair_cut_minus_comparison': number(difference)})
        for name, row in policies.items():
            cost = Fraction(row['expected']['cost']['exact'])
            ratios.append({'problem_id': pid, 'stratum': row['stratum'],
                           'subtype': row['subtype'], 'policy': name,
                           'optimal_cost': number(optimal),
                           'gap': number(cost - optimal),
                           'ratio': number(cost / optimal) if optimal else None,
                           'zero_optimal_cost': not bool(optimal)})
    return {'stratified': summaries, 'paired_cost_contrasts': contrasts,
            'optimal_comparisons': ratios, 'problems': len(by_problem),
            'policy_budget_rows': len(result['per_problem_policy_budget']),
            'signature_policy_budget_runs': len(result['runs']),
            'unique_certificates': len(result['certificates']),
            'charged_queries': result['charged_queries'],
            'certificate_failures': sum(not r['certificate_valid'] for r in result['runs'])}


def prepare():
    from .generator import generate_problem
    config = read(STUDY / 'config.json')
    paths = [STUDY / p for p in ('development_problems.json', 'evaluation_problems.json',
                                  'input_manifest.json')]
    if any(p.exists() for p in paths):
        raise FileExistsError('Prepared inputs already exist; refusing overwrite')
    development = [generate_problem(row['seed'], row['stratum'])
                   for row in config['development']]
    evaluation = [generate_problem(seed, row['name'])
                  for row in config['evaluation_strata'] for seed in row['seeds']]
    validate_inputs(development, 4)
    validate_inputs(evaluation, 40)
    write_new(paths[0], development)
    write_new(paths[1], evaluation)
    fingerprints = defaultdict(list)
    for p in evaluation:
        fingerprints[p['unweighted_structure_fingerprint']].append(p['problem_id'])
    write_new(paths[2], {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'selection': 'all declared seeds, no outcome-based selection/rejection or regeneration',
        'generation_failures': [], 'development_count': 4, 'evaluation_count': 40,
        'evaluation_policy_outcomes_observed': False,
        'files_sha256': {p.name: digest(p) for p in paths[:2]},
        'generator_sha256': digest(Path(__file__).with_name('generator.py')),
        'structural_fingerprints': [{k: p[k] for k in
            ('problem_id', 'seed', 'stratum', 'subtype', 'structural_fingerprint',
             'unweighted_structure_fingerprint')} for p in evaluation],
        'distinct_weighted_problems': len({p['structural_fingerprint'] for p in evaluation}),
        'distinct_unweighted_structures': len(fingerprints),
        'repeated_structures': {k: v for k, v in fingerprints.items() if len(v) > 1},
        'interpretation': 'Cost variants of one structure are not independent scientific problems.'})
    return {'development': 4, 'evaluation': 40, 'unweighted_structures': len(fingerprints)}


def validate_inputs(problems, count, expected=None):
    if len(problems) != count or len({p['problem_id'] for p in problems}) != count:
        raise ValueError('Wrong input problem count or duplicated identity')
    if expected is not None:
        identities = [(p['seed'], p['stratum'], p['split']) for p in problems]
        if identities != expected or any(p['problem_id'] != f"acq_{p['seed']}" for p in problems):
            raise ValueError('Prepared input identities differ from declared schedule')
    for p in problems:
        model = Model(p)
        if len(set(model.priors)) != 1:
            raise ValueError('Primary experiment requires uniform assignment prior')
    return count


def freeze_paths():
    modules = ['__init__.py', '__main__.py', 'model.py', 'generator.py',
               'certificates.py', 'policies.py', 'study.py']
    files = [ROOT / 'src/tracebench/__init__.py']
    files += [Path(__file__).parent / p for p in modules]
    files += [ROOT / 'tests' / p for p in ['test_acquisition_model.py',
              'test_acquisition_policies.py', 'test_acquisition_study.py']]
    files += [STUDY / p for p in ['config.json', 'ANALYSIS.md', 'METHOD.md',
              'evaluation_problems.json', 'development_problems.json',
              'input_manifest.json', 'development_results.json', 'pre_freeze_checks.json']]
    return files


def verify_freeze():
    frozen = read(STUDY / 'freeze.json')
    required = {str(p.relative_to(ROOT)) for p in freeze_paths()}
    if set(frozen['files_sha256']) != required:
        raise ValueError('Execution freeze dependency closure differs')
    for name, expected in frozen['files_sha256'].items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or digest(path) != expected:
            raise ValueError(f'Execution freeze mismatch: {name}')
    return frozen


def verify_prepared_inputs(config):
    from .generator import generate_problem
    manifest = read(STUDY / 'input_manifest.json')
    if digest(Path(__file__).with_name('generator.py')) != manifest['generator_sha256']:
        raise ValueError('Prepared generator source changed')
    expected = {
        'development': [(r['seed'], r['stratum'], 'development') for r in config['development']],
        'evaluation': [(seed, r['name'], 'evaluation')
                       for r in config['evaluation_strata'] for seed in r['seeds']]}
    if [x[0] for x in expected['development']] != list(range(94100, 94104)):
        raise ValueError('Wrong development seed schedule')
    if [x[0] for x in expected['evaluation']] != list(range(94200, 94240)):
        raise ValueError('Wrong evaluation seed schedule')
    for split, count in [('development', 4), ('evaluation', 40)]:
        name = split + '_problems.json'
        if digest(STUDY / name) != manifest['files_sha256'][name]:
            raise ValueError('Prepared input hash mismatch')
        problems = read(STUDY / name)
        validate_inputs(problems, count, expected[split])
        if problems != [generate_problem(seed, stratum) for seed, stratum, _ in expected[split]]:
            raise ValueError('Prepared inputs differ from fixed generator')
    if manifest['generation_failures']:
        raise ValueError('Recorded generation failure blocks complete evaluation')


def freeze():
    config = read(STUDY / 'config.json')
    verify_prepared_inputs(config)
    checks = read(STUDY / 'pre_freeze_checks.json')
    if checks['failures'] or not checks['phase_a_dependencies_isolated']:
        raise ValueError('Pre-freeze correctness/dependency checks have not passed')
    files = freeze_paths()
    record = {'schema_version': 1, 'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
              'files_sha256': {str(p.relative_to(ROOT)): digest(p) for p in files},
              'python_version': sys.version.split()[0],
              'evaluation_policy_outcomes_observed': False,
              'config': config, 'development_only_before_freeze': True}
    write_new(STUDY / 'freeze.json', record)
    return {'status': 'frozen', 'files': len(files)}


def develop():
    problems = read(STUDY / 'development_problems.json')
    validate_inputs(problems, 4)
    result = evaluate(problems, read(STUDY / 'config.json'))
    write_new(STUDY / 'development_results.json',
              {'summary': summarize(result), 'runtime': result['runtime'],
               'per_problem_policy_budget': result['per_problem_policy_budget']})
    return {'development_problems': 4, 'certificate_failures': summarize(result)['certificate_failures']}


def run(output):
    verify_freeze()
    output = Path(output)
    if output.exists():
        raise FileExistsError('Evaluation output already exists; refusing overwrite')
    output.mkdir(parents=True)
    started = perf_counter()
    try:
        result = evaluate(read(STUDY / 'evaluation_problems.json'), read(STUDY / 'config.json'))
    except Exception as error:
        write_new(output / 'failure.json', {'type': type(error).__name__, 'message': str(error),
                                           'frozen_inputs_preserved': True})
        raise
    summary = summarize(result)
    write_new(output / 'per_problem_policy_budget.json', result['per_problem_policy_budget'])
    write_new(output / 'summary.json', summary)
    write_new(output / 'runtime.json', {'problems': result['runtime'],
                                      'evaluation_seconds': perf_counter() - started,
                                      'cache_scope': 'one planner per problem and policy across signatures/budgets; runtime is pipeline cost, not independent query latency'})
    # Compact, lossless encodings keep large expanded histories out of tracked results.
    for name, value in [('certificates', result['certificates']), ('signature_runs', result['runs'])]:
        encoded = json.dumps(value, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False, allow_nan=False).encode('utf-8')
        with (output / (name + '.json.gz')).open('xb') as stream:
            stream.write(gzip.compress(encoded, mtime=0))
    write_new(output / 'manifest.json',
              {'freeze_sha256': digest(STUDY / 'freeze.json'),
               'files_sha256': {p.name: digest(p) for p in sorted(output.iterdir())},
               'completed_at_utc': datetime.now(timezone.utc).isoformat(),
               'network_requests': 0, 'model_calls': 0, 'additional_spend_usd': '0',
               'encoding': 'certificates.json.gz and signature_runs.json.gz are lossless UTF-8 JSON (gzip mtime=0); signature_index indexes lexicographically sorted Model.signature_cells. Certificates include exact acquired histories. All contents deliberately synthetic. Expand large histories only under ignored artifacts/evidence-acquisition.'})
    return {k: summary[k] for k in ('problems', 'policy_budget_rows',
                                   'signature_policy_budget_runs', 'charged_queries',
                                   'unique_certificates', 'certificate_failures')}
