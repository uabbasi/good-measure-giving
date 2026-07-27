"""Errors that distinguish an unreachable model from an unhelpful one."""


class LLMUnavailableError(RuntimeError):
    """Raised when an LLM call could not be completed at all.

    This is the transport layer failing — DNS, connection refused, timeout,
    auth, a provider outage — not the model returning something we dislike.
    The distinction is load-bearing, not pedantic.

    Enrichers in this pipeline are deliberately fail-closed: if the model says
    it cannot confirm a claim, we record "unverified" and move on. That is
    correct for an ANSWER. It is wrong for the absence of one. On 2026-07-26 a
    Gemini DNS failure ran through synthesize for all 166 charities, and a bare
    `except Exception` turned the outage into a verdict: beneficiary semantics
    were stamped `verified: False`, program focus tags came back empty, and
    because `CharityDataRepository.upsert` writes every field including None,
    both overwrote good data. program_focus_tags went from 0 NULL to 119 NULL,
    and 35 charities flipped to excluded-from-scoring — none of it because
    anything was actually learned about those charities.

    Raise this instead so the caller stops rather than persisting a conclusion
    nobody drew. Catch only around the call itself; a response that arrives and
    then fails to parse is still an answer, and fail-closed remains right there.
    """
