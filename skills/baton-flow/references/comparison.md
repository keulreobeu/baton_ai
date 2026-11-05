# Compare before keeping or replacing

Frame the candidate contract before implementation. Use the same requirements, fixtures, failure injections and acceptance checks for the current implementation and each proposed replacement. Keep code candidates isolated and pin their base/head identifiers.

Evaluate in this order:

1. Mandatory safety and observable behavior: ownership, boundaries, cancellation, stale evidence and restart behavior. A failure cannot be offset by speed or fewer lines.
2. Proven contract coverage and recoverability. A proposed path with no executable evidence remains unverified; an existing helper with the wrong contract also fails.
3. Duplicated authority/state, maintenance complexity, deployment dependencies and actual changed code.
4. Measured time/token cost when observed on comparable work. Do not invent a score or infer a speedup from model agreement.

Choose one coherent base and explain which alternatives lost each criterion. Port another candidate's useful part only if it improves the same contract; rerun the affected checks after grafting. If outputs diverge because the requirements were vague, refine the task instead of merging incompatible designs.

This is the reusable arena comparison method, not an arena execution engine or permission to launch extra model runs. Model diversity is helpful evidence; a reviewer vote is not user approval.
