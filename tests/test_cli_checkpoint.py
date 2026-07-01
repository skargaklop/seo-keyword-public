# MODULE_CONTRACT: tests/test_cli_checkpoint
# Purpose: TDD RED->GREEN for cli.checkpoint — the per-run checkpoint store that lets long paid-API
#   batches resume after a failure instead of re-paying for every step.
# Rationale: docs/cli-plan.md §6.1 + §7 Phase C2. Steps 3-7 (LLM/Ads/SERP/Trends) cost money/quota;
#   a checkpoint store saves each step's artifact and an input-hash so --resume skips done steps and
#   refuses to reuse an artifact whose input set changed (stale-guard).
# Dependencies: cli.checkpoint, pandas, pytest.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-032, verification-plan.xml#V-18-CHECKPOINT, docs/cli-plan.md §6.1
# MODULE_MAP: tests/test_cli_checkpoint.py
# Public Functions: pytest test functions.
# Private Helpers: none.
# Key Semantic Blocks: none.
# Critical Flows: save artifact -> reload -> equal; is_done; input-hash stale-guard; resume order.
# Verification: verification-plan.xml#V-18-CHECKPOINT
# CHANGE_SUMMARY: Phase C2 RED — artifact save/reload round-trip, done-detection, input-hash stale
#   guard (mismatched inputs reject the artifact), resume picks first incomplete step, clean() wipes.

from pathlib import Path

import pandas as pd
import pytest


def _kw(url_safe: str = "coffee") -> list[str]:
    return [url_safe]


def test_save_then_reload_artifact_round_trips(tmp_path: Path) -> None:
    from cli.checkpoint import CheckpointStore

    store = CheckpointStore(workdir=tmp_path, run_id="r1", keywords=_kw(), urls=[])
    df = pd.DataFrame({"Keyword": ["coffee", "tea"], "Volume": [10, 20]})
    store.save("ads", artifact=df)

    back = store.load("ads")
    pd.testing.assert_frame_equal(back, df)


def test_is_done_only_after_save(tmp_path: Path) -> None:
    from cli.checkpoint import CheckpointStore

    store = CheckpointStore(workdir=tmp_path, run_id="r1", keywords=_kw(), urls=[])
    assert not store.is_done("ads")
    store.save("ads", artifact=pd.DataFrame({"Keyword": ["coffee"]}))
    assert store.is_done("ads")


# An artifact saved for one input set must NOT be reused for a different input set.
def test_input_hash_mismatch_rejects_stale_artifact(tmp_path: Path) -> None:
    from cli.checkpoint import CheckpointStore

    store = CheckpointStore(workdir=tmp_path, run_id="r1", keywords=_kw("coffee"), urls=[])
    store.save("ads", artifact=pd.DataFrame({"Keyword": ["coffee"]}))

    # New run, different keywords, same run_id/workdir -> stale guard fires.
    other = CheckpointStore(workdir=tmp_path, run_id="r1", keywords=["espresso"], urls=[])
    assert not other.is_done("ads")
    assert other.load("ads") is None


# Same inputs + same run_id -> a fresh store sees the prior artifact as done (resume works).
def test_input_hash_match_allows_resume_across_processes(tmp_path: Path) -> None:
    from cli.checkpoint import CheckpointStore

    store = CheckpointStore(workdir=tmp_path, run_id="r1", keywords=_kw("coffee"), urls=[])
    store.save("ads", artifact=pd.DataFrame({"Keyword": ["coffee"]}))

    resumed = CheckpointStore(workdir=tmp_path, run_id="r1", keywords=_kw("coffee"), urls=[])
    assert resumed.is_done("ads")


def test_next_incomplete_returns_first_non_done_step(tmp_path: Path) -> None:
    from cli.checkpoint import CheckpointStore

    store = CheckpointStore(workdir=tmp_path, run_id="r1", keywords=_kw(), urls=[])
    all_steps = ["validate", "scrape", "ads", "serp", "trends", "merge"]
    assert store.next_incomplete(all_steps) == "validate"

    store.save("validate")
    store.save("scrape")
    assert store.next_incomplete(all_steps) == "ads"


def test_next_incomplete_returns_none_when_all_done(tmp_path: Path) -> None:
    from cli.checkpoint import CheckpointStore

    store = CheckpointStore(workdir=tmp_path, run_id="r1", keywords=_kw(), urls=[])
    steps = ["validate", "ads"]
    for s in steps:
        store.save(s)
    assert store.next_incomplete(steps) is None


def test_clean_wipes_workdir(tmp_path: Path) -> None:
    from cli.checkpoint import CheckpointStore

    store = CheckpointStore(workdir=tmp_path, run_id="r1", keywords=_kw(), urls=[])
    store.save("ads", artifact=pd.DataFrame({"Keyword": ["coffee"]}))
    assert store.is_done("ads")

    store.clean()
    assert not store.is_done("ads")
    assert store.load("ads") is None


# Some steps (validate) have no DataFrame artifact but should still checkpoint as done.
def test_artifact_without_dataframe_is_still_done(tmp_path: Path) -> None:
    from cli.checkpoint import CheckpointStore

    store = CheckpointStore(workdir=tmp_path, run_id="r1", keywords=_kw(), urls=[])
    store.save("validate")  # no artifact
    assert store.is_done("validate")
    assert store.load("validate") is None


# The checkpoint manifest lives at <workdir>/checkpoint-<run_id>.json.
def test_run_manifest_path_is_under_workdir(tmp_path: Path) -> None:
    from cli.checkpoint import CheckpointStore

    store = CheckpointStore(workdir=tmp_path, run_id="r42", keywords=_kw(), urls=[])
    assert Path(store.manifest_path).parent == tmp_path.resolve()
    assert Path(store.manifest_path).name == "checkpoint-r42.json"
