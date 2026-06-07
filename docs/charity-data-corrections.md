# Charity Data Corrections — Systemic Process

How we handle inbound corrections, disputes, and update requests from charities.
Referenced by the charity score report (`data-pipeline/charity_report.py`,
"Correcting or updating our data" section). The promise to charities: a defined
process, end-to-end re-runs (never hand-edited scores), and a full audit trail.

## Principles

1. **Scores only ever come from the pipeline.** No manual score edits, ever.
   A correction changes inputs (source data, parser, denylist); the score
   changes only by re-running.
2. **Every change is version-controlled.** DoltDB commits give a complete
   audit history per value and per score (`dolt_history_*` tables). When a
   charity asks "what changed and when," we can answer with a diff.
3. **One intake, three lanes.** Every inbound report is triaged into exactly
   one lane below, each with a defined fix path.

## Intake

- Channel: the contact path on goodmeasuregiving.org.
- Required from the charity: EIN, the specific data point, what it should be,
  and a public URL where the correct value is verifiable.
- Acknowledge receipt. Re-evaluations run periodically; a verified correction
  is reflected in the next evaluation cycle (the same language the score
  report uses — no fixed turnaround is promised).

## The three lanes

### Lane 1 — We misread a source (pipeline error)

The public source is right; our extraction is wrong.

1. Reproduce: `uv run python data_quality_check.py --ein <EIN> --verbose`
2. Fix the parser/extractor (or add the field to the hallucination denylist
   in `src/validators/hallucination_denylist.py` if it's an LLM-extraction
   reliability problem affecting more than this charity).
3. Re-run end-to-end: `uv run python streaming_runner.py --ein <EIN> --force-all`
4. DoltDB auto-commits per phase; add a descriptive manual commit if the fix
   was data-only: `dolt.commit("Correction: <EIN> <field> per charity report <date>")`
5. Export refreshes the website JSON; the charity's page and any future score
   report reflect the fix.

If the misread is systemic (same parser bug affects many EINs), fix once and
re-run the affected cohort, not just the reporting charity.

### Lane 2 — The data isn't public yet (charity-side gap)

We read the right sources; the charity hasn't published the information.

1. Point the charity at the **Sources table** in their score report — it names
   the exact source we read for each field (website page, Form 990, Candid,
   Charity Navigator).
2. The charity publishes (zakat policy page, beneficiary counts, board roster,
   audited financials, updated Candid profile).
3. They notify us; we re-run: `streaming_runner.py --ein <EIN> --force-all`
   (or `--force-phase discover` if only website content changed).
4. No pipeline change required. This is the most common lane and the score
   report is designed to make it self-service.

### Lane 3 — Methodology dispute

The data is right; the charity disagrees with how it's scored.

1. Log it as a GitHub issue with the charity's argument and concrete examples
   (see issue #1 — Cost Per Beneficiary vs. advocacy orgs — as the template).
2. No per-charity exceptions. Methodology changes apply to everyone or no one,
   and ship as rubric version bumps (semver: major = structural, minor =
   reweight, patch = bug fix) with a DoltDB tag cross-referencing the git tag.
3. Tell the charity the disposition honestly: logged for the next rubric
   review, with the issue link.

## Audit trail mechanics

- `dolt log` — every pipeline run and manual correction is a commit.
- `dolt diff <commit1> <commit2> evaluations` — exactly what a re-run changed.
- `SELECT * FROM dolt_history_evaluations WHERE charity_ein = '<EIN>'` — full
  score history for one charity.
- Rubric versions are tagged (`rubric-vX.Y.Z`) in both git and DoltDB, so any
  historical score can be tied to the rubric that produced it.

## Not built yet (decide before the volume arrives)

- **Manual overrides file** (e.g., `config/manual_corrections.yaml` applied at
  synthesize) for cases where a source is persistently wrong and unfixable at
  origin (a stale Candid value the charity can't get corrected). Deliberately
  not built: it weakens "scores only come from the pipeline" unless overrides
  are themselves versioned, attributed, and surfaced in the score report's
  Sources table. Revisit when the first real case arrives.
- **Public corrections form** instead of free-form contact. Worth it once
  inbound volume exceeds a few per month.
- **Auto-notification** to a charity when their score changes after a re-run.
