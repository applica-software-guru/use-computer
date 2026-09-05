---
title: "CI stops at a step that only prints versions, so nothing is tested"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-05T00:00:00.000Z"
---

# CI stops at a step that only prints versions, so nothing is tested

## What happens

```
Run uv run --no-sync python -c "import typer, rich, pydantic; print('typer', typer.__version__, …)"
AttributeError: module 'rich' has no attribute '__version__'
##[error]Process completed with exit code 1
```

Every matrix leg fails, on every push, **before pytest runs**. It has been failing since at least
the 0.2.2 release: that commit's CI run is red too, and the release went out anyway because
publishing is a separate workflow.

## Why

`rich` dropped its module-level `__version__`. The step is a diagnostic — it exists so a failure
further down can be read against the versions that produced it — and it is the only thing in CI
that reaches into a dependency's private surface. `tech-stack.md` already says why that is the
wrong move for `typer`, and the same argument applies here.

## Why it matters

Not the missing string: **the missing test run**. A workflow whose first real step is a `print`
turns a cosmetic upstream change into a total loss of signal, and a red tick that has been red for
days stops being read. The 0.3.0 work was written against a suite that CI had not run once.

## Expected

Versions come from `importlib.metadata.version(...)`, which is the packaging metadata rather than a
convention a library may drop. And the step cannot fail the job: a diagnostic that stops the tests
is worse than no diagnostic.
