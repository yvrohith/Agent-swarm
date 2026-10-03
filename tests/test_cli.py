import hashlib
import json

import pytest

from tracebench.cli import main


def test_benchmark_artifacts_and_repeatability(tmp_path):
    args = ["benchmark", "--seeds", "2", "--runs", "10", "--transmission", "0,0.3",
            "--shocks", "0.5", "--bootstrap-samples", "100"]
    first, second = tmp_path / "one", tmp_path / "two"
    main(args + ["--output", str(first)])
    main(args + ["--output", str(second)])
    result = json.loads((first / "benchmark.json").read_text())
    assert result["metadata"]["n_worlds"] == 4
    assert len(result["runs"]) == 40
    assert len(result["summary"]) == 20
    assert (first / "benchmark.json").read_bytes() == (second / "benchmark.json").read_bytes()
    manifest = json.loads((first / "manifest.json").read_text())
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((first / name).read_bytes()).hexdigest() == digest
    assert (first / "trace_completeness.png").stat().st_size > 1000
    assert (first / "trace_completeness.svg").read_text().find("<svg") != -1
    with pytest.raises(SystemExit) as error:
        main(args + ["--output", str(first)])
    assert error.value.code == 2


def test_equivalence_cli_reports_different_truth(capsys):
    main(["equivalence"])
    result = json.loads(capsys.readouterr().out)
    assert all(result["observations_equal"].values())
    assert result["world_a_truth_edges"] != result["world_b_truth_edges"]


@pytest.mark.parametrize("arguments", [
    ["--runs", "0"], ["--transmission", "nan"], ["--shocks", "0,0"],
    ["--bootstrap-samples", "1"],
])
def test_invalid_cli_arguments(arguments):
    with pytest.raises(SystemExit) as error:
        main(["benchmark", *arguments])
    assert error.value.code == 2
