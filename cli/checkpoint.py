# MODULE_CONTRACT: cli.checkpoint
# Purpose: Per-run checkpoint store for seos-cli — saves each pipeline step's artifact + an input
#   hash so a long paid-API batch can RESUME after a failure instead of re-paying for every step.
# Rationale: docs/cli-plan.md §6.1 + §7 Phase C2. Steps 3-7 (LLM/Ads/SERP/Trends) cost money/quota;
#   this store persists per-step output and refuses to reuse an artifact whose input set changed.
# Design:
#   - Manifest at <workdir>/checkpoint-<run_id>.json: {"input_hash": "...", "steps": {name: {...}}}.
#   - DataFrame artifacts saved as sibling .json files (round-trip via pandas; reuses pandas/openpyxl,
#     NO new pip package — parquet would need pyarrow which is not a declared dependency).
#   - The input_hash is derived from keywords+urls; on resume, a mismatched hash rejects the artifact
#     (stale-guard) so a different input set never inherits another run's results.
# Dependencies: stdlib hashlib/json/pathlib + pandas + utils.logger (all streamlit-free).
#   NEVER streamlit/utils.pipeline/config.i18n.
# Exports: CheckpointStore.
# LINKS: knowledge-graph.xml#MOD-032, verification-plan.xml#V-18-CHECKPOINT, docs/cli-plan.md §6.1
# MODULE_MAP: cli/checkpoint.py
# Public Functions: CheckpointStore (save, load, is_done, next_incomplete, clean, manifest_path).
# Private Helpers: _compute_input_hash, _artifact_path, _df_to_file, _df_from_file.
# Key Semantic Blocks: none.
# Critical Flows: save(step, df?) -> manifest+artifact on disk -> is_done/next_incomplete consult
#   manifest + input-hash guard -> load(step) returns DataFrame or None.
# Verification: verification-plan.xml#V-18-CHECKPOINT
# CHANGE_SUMMARY: Phase C2 GREEN — CheckpointStore with JSON manifest + JSON DataFrame artifacts;
#   input-hash stale-guard; next_incomplete() resume ordering; clean() wipe; no new pip package.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from utils.logger import logger

DONE = "done"


# Stable hash of the input set so a changed input is detected on resume.
#
# Sorted so keyword/url order doesn't matter (a set change is what invalidates artifacts).
def _compute_input_hash(keywords: List[str], urls: List[str]) -> str:
    payload = json.dumps(
        {"keywords": sorted(keywords or []), "urls": sorted(urls or [])},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# Persistent per-run checkpoint of pipeline step artifacts.
#
# `workdir` is created on first save. `run_id` namespaces the manifest file. `keywords`/`urls`
# are the input set — their hash guards against reusing an artifact saved for different inputs.
class CheckpointStore:

    def __init__(
        self,
        workdir: Path,
        run_id: str,
        keywords: Optional[List[str]] = None,
        urls: Optional[List[str]] = None,
    ) -> None:
        self.workdir = Path(workdir)
        self.run_id = run_id
        self.input_hash = _compute_input_hash(keywords or [], urls or [])
        self.manifest_path = str(self.workdir / f"checkpoint-{run_id}.json")

    # ------------------------------------------------------------------ manifest IO

    def _read_manifest(self) -> Dict[str, Any]:
        try:
            return json.loads(Path(self.manifest_path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"input_hash": self.input_hash, "steps": {}}
        except Exception as exc:  # noqa: BLE001 — corrupt manifest: start clean
            logger.warning(f"cli: checkpoint manifest unreadable, starting fresh: {exc}")
            return {"input_hash": self.input_hash, "steps": {}}

    def _write_manifest(self, data: Dict[str, Any]) -> None:
        self.workdir.mkdir(parents=True, exist_ok=True)
        data["input_hash"] = self.input_hash
        Path(self.manifest_path).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------ artifacts

    def _artifact_path(self, step: str) -> Path:
        return self.workdir / f"artifact-{self.run_id}-{step}.json"

    def _df_to_file(self, df: pd.DataFrame, path: Path) -> None:
        df.to_json(path, orient="records", force_ascii=False, indent=2)

    def _df_from_file(self, path: Path) -> Optional[pd.DataFrame]:
        if not path.exists():
            return None
        try:
            return pd.read_json(path, orient="records")
        except Exception as exc:  # noqa: BLE001 — corrupt artifact: treat as absent
            logger.warning(f"cli: checkpoint artifact unreadable ({path}): {exc}")
            return None

    # ------------------------------------------------------------------ public API

    # Persist `step` as done, optionally saving its DataFrame artifact.
    def save(self, step: str, artifact: Optional[pd.DataFrame] = None) -> None:
        data = self._read_manifest()
        steps = data.setdefault("steps", {})
        entry: Dict[str, Any] = {"status": DONE}
        if artifact is not None:
            self.workdir.mkdir(parents=True, exist_ok=True)
            self._df_to_file(artifact, self._artifact_path(step))
            entry["artifact"] = self._artifact_path(step).name
            entry["rows"] = int(len(artifact))
        steps[step] = entry
        self._write_manifest(data)

    # Return the step's DataFrame artifact, or None if absent / stale / not done.
    def load(self, step: str) -> Optional[pd.DataFrame]:
        if not self.is_done(step):
            return None
        data = self._read_manifest()
        entry = data.get("steps", {}).get(step, {})
        art_name = entry.get("artifact")
        if not art_name:
            return None
        return self._df_from_file(self.workdir / art_name)

    # True only if the step is marked done AND the input-hash still matches.
    def is_done(self, step: str) -> bool:
        data = self._read_manifest()
        if data.get("input_hash") != self.input_hash:
            return False  # stale: artifact was saved for a different input set
        entry = data.get("steps", {}).get(step, {})
        return entry.get("status") == DONE

    # First step in `steps` that is not done, or None if all are done.
    def next_incomplete(self, steps: List[str]) -> Optional[str]:
        for step in steps:
            if not self.is_done(step):
                return step
        return None

    # Wipe this run's manifest + artifacts (a fresh start). Idempotent if nothing exists.
    def clean(self) -> None:
        manifest = Path(self.manifest_path)
        if manifest.exists():
            manifest.unlink()
        for p in self.workdir.glob(f"artifact-{self.run_id}-*.json"):
            try:
                p.unlink()
            except OSError as exc:  # noqa: BLE001
                logger.warning(f"cli: could not remove checkpoint artifact {p}: {exc}")
