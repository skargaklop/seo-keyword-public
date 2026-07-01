# MODULE_CONTRACT: tests/test_cli_pipeline
# Purpose: TDD coverage for cli.pipeline — headless stage orchestration (docs/cli-plan.md §3, §7 B).
# Rationale: the enrich pipeline must call the 7 streamlit-free utils/ stage callables in order and
#   thread a pd.DataFrame through to the merge step, WITHOUT importing/calling any Streamlit API.
# Process-isolation note: cli.pipeline transitively imports the utils/ stage modules (which is fine —
#   they are streamlit-free), but exercising run_enrichment in the pytest process perturbs shared
#   global state that later streamlit-based tests depend on (ordering-dependent failures). So each
#   orchestration scenario runs in an ISOLATED SUBPROCESS that injects plain fake stage callables
#   via dependency injection (no unittest.mock in the main process). The independence gate
#   (no streamlit import) is covered separately in test_cli_independence.py (also subprocess).
# Dependencies: cli.pipeline (subprocess), pandas, pytest.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-032, verification-plan.xml#V-18-PIPELINE, docs/cli-plan.md §3
# MODULE_MAP: tests/test_cli_pipeline.py
# Public Functions: pytest test functions.
# Private Helpers: _run_scenario (subprocess harness).
# Key Semantic Blocks: none.
# Critical Flows: run_enrichment(...) with injected fakes -> ordered stages -> merged DataFrame.
# Verification: verification-plan.xml#V-18-PIPELINE
# CHANGE_SUMMARY: Phase B RED->GREEN — orchestration scenarios run in subprocess with DI fakes;
#   asserts step ordering, DataFrame threading, keyword-only path (no scrape), and steps subset.
#   Added _inject_stages DI param to run_enrichment to support fakes without process-wide mocking.

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Run an enrichment scenario in an isolated subprocess with fake stage callables injected.
#
# The subprocess: imports cli.pipeline, monkeypatches the stage callables via the
# `_inject_stages` DI hook on run_enrichment, runs it, and prints JSON: {order, merged_cols,
# merge_received_keyword_col, scrape_called, trends_called, llm_called, error}.
def _run_scenario(scenario: str, config_overrides: Dict[str, Any]) -> Dict[str, Any]:
    overrides_json = json.dumps(config_overrides)
    code = (
        "import json, sys\n"
        "import pandas as pd\n"
        "import cli.pipeline as P\n"
        f"scenario = {scenario!r}\n"
        f"overrides = json.loads({overrides_json!r})\n"
        "calls = []\n"
        "def fake_validate(urls):\n"
        "    calls.append('validate')\n"
        "    return (list(urls), [])\n"
        "def fake_scrape(urls, **k):\n"
        "    calls.append('scrape')\n"
        "    from types import SimpleNamespace\n"
        "    return [SimpleNamespace(url=u, text='coffee tea beans', success=True) for u in urls]\n"
        "class FakeLLM:\n"
        "    def generate_keywords(self, text, **k):\n"
        "        calls.append('llm-extract'); return ['coffee','tea']\n"
        "    def generate_seo_text(self, *a, **k):\n"
        "        calls.append('seo-text'); return 'SEO COPY'\n"
        "class FakeAds:\n"
        "    def __init__(self, **k):\n"
        "        pass\n"
        "    def get_keyword_metrics(self, kws, **k):\n"
        "        calls.append('ads')\n"
        "        return pd.DataFrame({'Keyword': list(kws), 'Volume': [10]*len(kws)})\n"
        "    def get_keyword_ideas(self, *a, **k):\n"
        "        return pd.DataFrame({'Keyword':['coffee']})\n"
        "class FakeSerpClient:\n"
        "    def search_batch(self, q, **k):\n"
        "        calls.append('serp'); return []\n"
        "class FakeTrends:\n"
        "    def run_trends(self, kws, **k):\n"
        "        calls.append('trends'); return object()\n"
        "def fake_serp_factory(*a, **k):\n"
        "    return FakeSerpClient()\n"
        "def fake_merge(ads_df, **k):\n"
        "    calls.append('merge')\n"
        "    state['merge_df'] = ads_df\n"
        "    return ads_df\n"
        "def fake_write(df, out, fmt, seo_text=None):\n"
        "    calls.append('export'); return out\n"
        "state = {'merge_df': None}\n"
        "stages = {\n"
        "    'validate_urls': fake_validate,\n"
        "    'scrape_urls': fake_scrape,\n"
        "    'LLMHandler': FakeLLM,\n"
        "    'GoogleAdsHandler': FakeAds,\n"
        "    'create_serp_client': fake_serp_factory,\n"
        "    'TrendsOrchestrator': FakeTrends,\n"
        "    'merge_enrichment': fake_merge,\n"
        "    'write_report': fake_write,\n"
        "}\n"
        "base = dict(keywords=['coffee','tea'], urls=[], language='en',\n"
        "             llm_provider='openai', llm_model='gpt-test', serp_provider='serper_dev',\n"
        "             out='report.xlsx', fmt='xlsx', max_keywords=None, steps=None)\n"
        "base.update(overrides)\n"
        "cfg = P.EnrichmentConfig(**base)\n"
        "try:\n"
        "    merged = P.run_enrichment(cfg, _inject_stages=stages)\n"
        "    err = None\n"
        "except Exception as e:\n"
        "    import traceback; err = traceback.format_exc(); merged = None\n"
        "merge_df_cols = list(state['merge_df'].columns) if state['merge_df'] is not None else None\n"
        "out = {\n"
        "    'order': calls,\n"
        "    'merged_is_none': merged is None,\n"
        "    'merge_df_cols': merge_df_cols,\n"
        "    'merge_has_keyword': state['merge_df'] is not None and 'Keyword' in state['merge_df'].columns,\n"
        "    'error': err,\n"
        "}\n"
        "print(json.dumps(out, default=str))\n"
    )
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(PROJECT_ROOT)}
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"scenario subprocess failed (rc={result.returncode}):\n"
            f"STDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
        )
    lines = [line for line in result.stdout.strip().splitlines() if line.strip().startswith("{")]
    assert lines, f"no JSON output. stdout={result.stdout}\nstderr={result.stderr}"
    return json.loads(lines[-1])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _ordered(seq, *needles):
    idx = 0
    for n in needles:
        pos = seq.index(n, idx) if n in seq[idx:] else -1
        assert pos >= 0, f"{n!r} not found after prior steps in {seq}"
        idx = pos + 1
    return True


# run_enrichment must invoke the stage callables in documented order.
def test_pipeline_calls_stage_callables_in_order():
    data = _run_scenario("full", {"urls": ["https://example.com"]})
    assert data["error"] is None, data["error"]
    order = data["order"]
    # validate -> scrape -> llm-extract -> ads -> serp -> trends -> seo-text -> merge -> export
    _ordered(order, "scrape", "llm-extract", "ads", "serp", "trends", "seo-text", "merge", "export")


# generate_seo_text must receive keywords as [{'Keyword': ..., ...}] rows (the app's contract).
#
# utils/llm_handler.LLMHandler.generate_seo_text reads k['Keyword'] (capital K) — it expects
# Ads-DataFrame rows, not bare strings. A lowercase {'keyword': str} payload raises KeyError
# 'Keyword' (real bug observed in the end-to-end smoke run). This test locks the corrected shape.
def test_pipeline_seo_text_keyword_payload_uses_capital_keyword_dict():
    code = (
        "import json, sys\n"
        "import pandas as pd\n"
        "import cli.pipeline as P\n"
        "captured = {}\n"
        "class FakeLLM:\n"
        "    def generate_keywords(self, text, **k):\n"
        "        return []\n"
        "    def generate_seo_text(self, *a, **k):\n"
        "        captured['kw'] = k.get('keywords')\n"
        "        return 'SEO COPY'\n"
        "class FakeAds:\n"
        "    def __init__(self, **k):\n"
        "        pass\n"
        "    def get_keyword_metrics(self, kws, **k):\n"
        "        return pd.DataFrame({'Keyword': list(kws),\n"
        "                             'Avg Monthly Searches': [100]*len(kws)})\n"
        "stages = {'LLMHandler': FakeLLM, 'GoogleAdsHandler': FakeAds,\n"
        "          'create_serp_client': lambda *a, **k: None,\n"
        "          'write_report': lambda *a, **k: 'noop'}\n"
        "cfg = P.EnrichmentConfig(keywords=['coffee','tea'], urls=[],\n"
        "                          out='r.xlsx', fmt='xlsx')\n"
        "try:\n"
        "    P.run_enrichment(cfg, _inject_stages=stages)\n"
        "    err = None\n"
        "except Exception as e:\n"
        "    import traceback; err = traceback.format_exc()\n"
        "out = {'kw': captured.get('kw'), 'error': err}\n"
        "print(json.dumps(out, default=str))\n"
    )
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(PROJECT_ROOT)}
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), env=env,
    )
    assert result.returncode == 0, (
        f"subprocess failed:\nSTDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
    )
    lines = [line for line in result.stdout.strip().splitlines() if line.strip().startswith("{")]
    data = json.loads(lines[-1])
    assert data["error"] is None, f"seo-text stage errored: {data['error']}"
    kw = data["kw"]
    assert kw, f"generate_seo_text was not passed a keywords payload: {kw}"
    # The contract: list of dicts each with a capital 'Keyword' key.
    assert all(isinstance(d, dict) and "Keyword" in d for d in kw), (
        f"seo-text payload must be dicts with 'Keyword' key; got {kw}"
    )


# The ads DataFrame (with Keyword col) must reach merge_enrichment.
def test_pipeline_threads_dataframe_into_merge():
    data = _run_scenario("keywords_only", {"keywords": ["coffee"], "urls": []})
    assert data["error"] is None, data["error"]
    assert data["merge_has_keyword"], f"merge did not receive Keyword col: {data}"


# Keywords-only run (no URLs) must not call the scraper.
def test_pipeline_keyword_seed_path_no_scrape():
    data = _run_scenario("kw_no_scrape", {"keywords": ["coffee"], "urls": []})
    assert data["error"] is None, data["error"]
    assert "scrape" not in data["order"], f"scrape should not run: {data['order']}"


# --steps ads,serp must run only those stages (skip trends/llm-extract).
def test_pipeline_respects_steps_subset():
    data = _run_scenario(
        "subset", {"keywords": ["coffee"], "urls": [], "steps": ["ads", "serp", "merge", "export"]}
    )
    assert data["error"] is None, data["error"]
    order = data["order"]
    assert "trends" not in order, f"trends should not run: {order}"
    assert "llm-extract" not in order, f"llm-extract should not run: {order}"
    assert "ads" in order and "serp" in order


# ---------------------------------------------------------------------------
# Checkpoint integration (Phase C2) — resume skips done steps; clean wipes.
# ---------------------------------------------------------------------------

# Run an enrichment with the real checkpoint store in a subprocess, return {order, error}.
#
# First call populates the checkpoint; a second call with resume=run_id should NOT re-call the
# 'ads' stage (it's already done) unless clean=True.
def _run_checkpoint_scenario(tmp_path, keywords, *, resume=None, clean=False, run_id="r1"):
    workdir = str(tmp_path)
    code = (
        "import json, sys\n"
        "import pandas as pd\n"
        "import cli.pipeline as P\n"
        f"keywords = {keywords!r}\n"
        f"workdir = {workdir!r}\n"
        f"resume = {resume!r}\n"
        f"clean = {clean!r}\n"
        f"run_id = {run_id!r}\n"
        + _FAKE_STAGE_DEFS
        + "stages = {\n"
        "    'GoogleAdsHandler': FakeAds,\n"
        "    'create_serp_client': fake_serp_factory,\n"
        "    'TrendsOrchestrator': FakeTrends,\n"
        "    'merge_enrichment': fake_merge,\n"
        "    'write_report': fake_write,\n"
        "}\n"
        "cfg = P.EnrichmentConfig(keywords=keywords, urls=[], out='r.xlsx', fmt='json',\n"
        "                          workdir=workdir, resume=resume, clean=clean)\n"
        "cfg.__dict__['run_id'] = run_id\n"
        "try:\n"
        "    P.run_enrichment(cfg, _inject_stages=stages)\n"
        "    err = None\n"
        "except Exception as e:\n"
        "    import traceback; err = traceback.format_exc()\n"
        "print(json.dumps({'order': calls, 'error': err}, default=str))\n"
    )
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(PROJECT_ROOT)}
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), env=env,
    )
    if result.returncode != 0:
        raise AssertionError(f"subprocess failed:\nSTDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}")
    lines = [line for line in result.stdout.strip().splitlines() if line.strip().startswith("{")]
    return json.loads(lines[-1])


_FAKE_STAGE_DEFS = (
    "calls = []\n"
    "class FakeAds:\n"
    "    def __init__(self, **k):\n"
    "        pass\n"
    "    def get_keyword_metrics(self, kws, **k):\n"
    "        calls.append('ads')\n"
    "        return pd.DataFrame({'Keyword': list(kws), 'Volume': [10]*len(kws)})\n"
    "class FakeSerpClient:\n"
    "    def search_batch(self, q, **k):\n"
    "        calls.append('serp'); return []\n"
    "class FakeTrends:\n"
    "    def run_trends(self, kws, **k):\n"
    "        calls.append('trends'); return object()\n"
    "def fake_serp_factory(*a, **k):\n"
    "    return FakeSerpClient()\n"
    "def fake_merge(ads_df, **k):\n"
    "    calls.append('merge'); return ads_df\n"
    "def fake_write(df, out, fmt, seo_text=None):\n"
    "    calls.append('export'); return out\n"
)


# On resume, the 'ads' stage (already checkpointed done) is NOT re-invoked.
def test_pipeline_checkpoint_resume_skips_done_ads_stage(tmp_path):
    # First run: populates the checkpoint.
    first = _run_checkpoint_scenario(tmp_path, ["coffee", "tea"], run_id="r1")
    assert first["error"] is None, first["error"]
    assert "ads" in first["order"]

    # Second run, same inputs, resume=r1: ads must be skipped (already done + input hash matches).
    second = _run_checkpoint_scenario(
        tmp_path, ["coffee", "tea"], resume="r1", run_id="r1"
    )
    assert second["error"] is None, second["error"]
    assert "ads" not in second["order"], (
        f"resume re-ran ads; order={second['order']}"
    )


# --clean wipes the checkpoint, so even a resume re-runs every stage.
def test_pipeline_checkpoint_clean_re_runs_all(tmp_path):
    first = _run_checkpoint_scenario(tmp_path, ["coffee"], run_id="r1")
    assert "ads" in first["order"]

    cleaned = _run_checkpoint_scenario(
        tmp_path, ["coffee"], resume="r1", clean=True, run_id="r1"
    )
    assert cleaned["error"] is None, cleaned["error"]
    assert "ads" in cleaned["order"], (
        f"clean should re-run ads; order={cleaned['order']}"
    )


# A different input set must re-run ads even with resume (input-hash stale guard).
def test_pipeline_checkpoint_stale_input_re_runs(tmp_path):
    first = _run_checkpoint_scenario(tmp_path, ["coffee"], run_id="r1")
    assert "ads" in first["order"]

    # Different keywords -> different input hash -> stale guard fires -> ads re-runs.
    stale = _run_checkpoint_scenario(
        tmp_path, ["espresso"], resume="r1", run_id="r1"
    )
    assert stale["error"] is None, stale["error"]
    assert "ads" in stale["order"], (
        f"stale input should re-run ads; order={stale['order']}"
    )


# Export failure must surface back to cli.main so the process exits non-zero.
def test_pipeline_export_failure_returns_result_with_error_flag() -> None:
    code = (
        "import json\n"
        "import pandas as pd\n"
        "import cli.pipeline as P\n"
        "stages = {\n"
        "  'GoogleAdsHandler': type('FakeAds', (), {\n"
        "      '__init__': lambda self, **k: None,\n"
        "      'get_keyword_metrics': lambda self, kws, **k: pd.DataFrame({'Keyword': list(kws)})\n"
        "  }),\n"
        "  'write_report': lambda *a, **k: None,\n"
        "}\n"
        "cfg = P.EnrichmentConfig(keywords=['coffee'], urls=[], out='r.xlsx', fmt='xlsx')\n"
        "result = P.run_enrichment(cfg, _inject_stages=stages)\n"
        "print(json.dumps({'export_failed': getattr(result, 'export_failed', None)}, default=str))\n"
    )
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(PROJECT_ROOT)}
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), env=env,
    )
    assert result.returncode == 0, (
        f"subprocess failed:\nSTDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
    )
    lines = [line for line in result.stdout.strip().splitlines() if line.strip().startswith("{")]
    data = json.loads(lines[-1])
    assert data["export_failed"] is True
