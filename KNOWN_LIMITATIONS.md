# Known Limitations

- LinkedIn may change selectors, labels, or flows at any time. Update `config/config.yaml` selectors when that happens.
- Automation may violate LinkedIn terms or trigger account controls. This project does not claim undetectable automation.
- Acceptance detection is heuristic because LinkedIn does not expose a stable public browser API for this workflow.
- Withdrawal behavior is disabled by default and should be tested carefully before enabling.
- Recent activity and mutual connection visibility depend on privacy settings and LinkedIn layout variants.
- Docker headful browser operation can require host display configuration. Local Python is recommended for initial setup.
- LLM output is reviewed and validated, but users should still inspect outputs before running non-dry-run automation.
- Google Sheets updates are row-based; avoid sorting the sheet during a running job.
