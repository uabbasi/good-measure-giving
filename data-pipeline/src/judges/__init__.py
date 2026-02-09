"""Judge System for post-export validation.

Two judge categories:

**Deterministic judges** — pure Python, rule-based, fully reproducible:
- BasicInfoJudge: Essential charity info (mission, location)
- DataCompletenessJudge: Data source availability (website, etc.)
- RecognitionDataJudge: Awards/recognition accuracy (CN beacons, Candid seals)
- CrawlQualityJudge: Crawl-phase integrity (EIN matches, financial sanity)
- ExtractQualityJudge: Extract-phase integrity (schema types, numeric bounds)
- DiscoverQualityJudge: Discover-phase integrity (confidence, source domains)
- SynthesizeQualityJudge: Synthesize-phase integrity (financial ratios, attribution)
- BaselineQualityJudge: Baseline-phase integrity (score bounds, wallet tags)
- ExportQualityJudge: Export-phase JSON structure (pillar scores, consistency)

**LLM judges** — use LLM for semantic validation, non-deterministic:
- CitationJudge: Verifies URL content supports narrative claims
- FactualJudge: Verifies narrative claims match source data
- ScoreJudge: Verifies rationale-score alignment
- ZakatJudge: Verifies zakat classification vs actual programs
- NarrativeQualityJudge: Assesses specificity, actionability, genuineness
- CrossLensJudge: Finds contradictions across narrative lenses

Usage:
    from judges import JudgeOrchestrator, JudgeConfig

    orchestrator = JudgeOrchestrator(JudgeConfig(sample_rate=0.1))
    result = orchestrator.validate_batch(exported_charities)
"""

from .base_judge import JudgeType
from .diff_validator import ChangeRecord, DiffValidationReport, DiffValidator
from .orchestrator import BatchResult, JudgeOrchestrator
from .schemas.config import JudgeConfig
from .schemas.verdict import JudgeVerdict, ScoreChangeSeverity, Severity, ValidationIssue

__all__ = [
    "JudgeConfig",
    "JudgeType",
    "JudgeVerdict",
    "ValidationIssue",
    "Severity",
    "ScoreChangeSeverity",
    "JudgeOrchestrator",
    "BatchResult",
    "DiffValidator",
    "DiffValidationReport",
    "ChangeRecord",
]
