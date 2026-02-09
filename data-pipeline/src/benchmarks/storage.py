"""
Benchmark storage - Save and load benchmark runs.

Results are stored as JSON in results/{run_id}/ for git versioning.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

RESULTS_DIR = Path(__file__).parent / "results"


@dataclass
class CharityEvaluation:
    """Single charity evaluation output."""

    ein: str
    name: str
    amal_score: Optional[int]
    wallet_tag: Optional[str]
    confidence_tier: Optional[str]
    impact_tier: Optional[str]
    score_details: Optional[dict[str, Any]]
    baseline_narrative: Optional[dict[str, Any]]
    llm_cost_usd: float = 0.0
    latency_seconds: float = 0.0
    error: Optional[str] = None
    # LLM quality metrics (rule-based)
    quality_metrics: Optional[dict[str, Any]] = None


@dataclass
class BenchmarkRun:
    """A complete benchmark run with metadata and results."""

    run_id: str
    model: str
    prompt_name: str
    prompt_version: str
    prompt_hash: str
    timestamp: str
    charities_count: int
    charities_succeeded: int = 0
    charities_failed: int = 0
    total_cost_usd: float = 0.0
    total_latency_seconds: float = 0.0
    evaluations: list[CharityEvaluation] = field(default_factory=list)
    notes: str = ""

    @property
    def success_rate(self) -> float:
        """Percentage of charities successfully evaluated."""
        if self.charities_count == 0:
            return 0.0
        return self.charities_succeeded / self.charities_count * 100

    @property
    def avg_cost_per_charity(self) -> float:
        """Average cost per charity in USD."""
        if self.charities_succeeded == 0:
            return 0.0
        return self.total_cost_usd / self.charities_succeeded

    @property
    def avg_latency_per_charity(self) -> float:
        """Average latency per charity in seconds."""
        if self.charities_succeeded == 0:
            return 0.0
        return self.total_latency_seconds / self.charities_succeeded

    def to_summary(self) -> dict[str, Any]:
        """Generate summary statistics."""
        scores = [e.amal_score for e in self.evaluations if e.amal_score is not None]

        # Aggregate LLM quality metrics
        quality_metrics = [
            e.quality_metrics for e in self.evaluations
            if e.quality_metrics is not None
        ]
        llm_quality = {}
        if quality_metrics:
            n = len(quality_metrics)
            llm_quality = {
                "count": n,
                "avg_structural": round(sum(q.get("structural_score", 0) for q in quality_metrics) / n, 1),
                "avg_citation": round(sum(q.get("citation_score", 0) for q in quality_metrics) / n, 1),
                "avg_specificity": round(sum(q.get("specificity_score", 0) for q in quality_metrics) / n, 1),
                "avg_completeness": round(sum(q.get("completeness_score", 0) for q in quality_metrics) / n, 1),
                "avg_overall": round(sum(q.get("overall_score", 0) for q in quality_metrics) / n, 1),
            }

        return {
            "run_id": self.run_id,
            "model": self.model,
            "prompt": f"{self.prompt_name}@{self.prompt_version}",
            "prompt_hash": self.prompt_hash,
            "timestamp": self.timestamp,
            "charities": {
                "total": self.charities_count,
                "succeeded": self.charities_succeeded,
                "failed": self.charities_failed,
                "success_rate": f"{self.success_rate:.1f}%",
            },
            "cost": {
                "total_usd": round(self.total_cost_usd, 4),
                "avg_per_charity_usd": round(self.avg_cost_per_charity, 4),
            },
            "latency": {
                "total_seconds": round(self.total_latency_seconds, 1),
                "avg_per_charity_seconds": round(self.avg_latency_per_charity, 2),
            },
            "scores": {
                "count": len(scores),
                "min": min(scores) if scores else None,
                "max": max(scores) if scores else None,
                "mean": round(sum(scores) / len(scores), 1) if scores else None,
            },
            "llm_quality": llm_quality,
            "notes": self.notes,
        }


class BenchmarkStorage:
    """Save and load benchmark runs."""

    def __init__(self, results_dir: Optional[Path] = None):
        """Initialize storage.

        Args:
            results_dir: Directory to store results. Defaults to results/ in this module.
        """
        self.results_dir = results_dir or RESULTS_DIR
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def generate_run_id(self, model: str, prompt_name: str, prompt_version: str) -> str:
        """Generate a unique run ID.

        Format: YYYY-MM-DD_model_prompt-version
        Example: 2026-01-24_gemini-3-flash_baseline-v2.0.0
        """
        date = datetime.now().strftime("%Y-%m-%d")
        # Sanitize model name (remove slashes, etc.)
        model_clean = model.replace("/", "-").replace(":", "-")
        return f"{date}_{model_clean}_{prompt_name}-v{prompt_version}"

    def save(self, run: BenchmarkRun) -> Path:
        """Save a benchmark run to disk.

        Creates:
        - results/{run_id}/metadata.json - Run configuration
        - results/{run_id}/evaluations.json - Full evaluation outputs
        - results/{run_id}/summary.json - Aggregate statistics

        Returns:
            Path to the run directory
        """
        run_dir = self.results_dir / run.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Metadata (everything except evaluations)
        metadata = {
            "run_id": run.run_id,
            "model": run.model,
            "prompt_name": run.prompt_name,
            "prompt_version": run.prompt_version,
            "prompt_hash": run.prompt_hash,
            "timestamp": run.timestamp,
            "charities_count": run.charities_count,
            "charities_succeeded": run.charities_succeeded,
            "charities_failed": run.charities_failed,
            "total_cost_usd": run.total_cost_usd,
            "total_latency_seconds": run.total_latency_seconds,
            "notes": run.notes,
        }
        self._write_json(run_dir / "metadata.json", metadata)

        # Evaluations (full outputs, sorted by EIN for stable diffs)
        evaluations = sorted(
            [asdict(e) for e in run.evaluations],
            key=lambda x: x["ein"],
        )
        self._write_json(run_dir / "evaluations.json", evaluations)

        # Summary (human-readable stats)
        summary = run.to_summary()
        self._write_json(run_dir / "summary.json", summary)

        return run_dir

    def load(self, run_id: str) -> Optional[BenchmarkRun]:
        """Load a benchmark run from disk.

        Args:
            run_id: The run ID to load

        Returns:
            BenchmarkRun or None if not found
        """
        run_dir = self.results_dir / run_id
        if not run_dir.exists():
            return None

        metadata_path = run_dir / "metadata.json"
        evaluations_path = run_dir / "evaluations.json"

        if not metadata_path.exists():
            return None

        metadata = self._read_json(metadata_path)
        evaluations_data = self._read_json(evaluations_path) if evaluations_path.exists() else []

        evaluations = [CharityEvaluation(**e) for e in evaluations_data]

        return BenchmarkRun(
            run_id=metadata["run_id"],
            model=metadata["model"],
            prompt_name=metadata["prompt_name"],
            prompt_version=metadata["prompt_version"],
            prompt_hash=metadata["prompt_hash"],
            timestamp=metadata["timestamp"],
            charities_count=metadata["charities_count"],
            charities_succeeded=metadata.get("charities_succeeded", 0),
            charities_failed=metadata.get("charities_failed", 0),
            total_cost_usd=metadata.get("total_cost_usd", 0.0),
            total_latency_seconds=metadata.get("total_latency_seconds", 0.0),
            evaluations=evaluations,
            notes=metadata.get("notes", ""),
        )

    def list_runs(self) -> list[str]:
        """List all available run IDs, sorted by date (newest first)."""
        runs = []
        for path in self.results_dir.iterdir():
            if path.is_dir() and (path / "metadata.json").exists():
                runs.append(path.name)
        return sorted(runs, reverse=True)

    def _write_json(self, path: Path, data: Any) -> None:
        """Write JSON with consistent formatting for git diffs."""
        with open(path, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")  # Trailing newline for git

    def _read_json(self, path: Path) -> Any:
        """Read JSON file."""
        with open(path) as f:
            return json.load(f)
