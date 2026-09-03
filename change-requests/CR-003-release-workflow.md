---
title: "Split CI from publishing, and rehearse releases on TestPyPI"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-03T00:00:00.000Z"
---

# Split CI from publishing, and rehearse releases on TestPyPI

## Why

Three reasons, in order of how much they cost when ignored.

**A release cannot be rehearsed.** Today the only path to the publish job is publishing a GitHub
release, and PyPI never lets a version be reused. A mistake in the pipeline is discovered by
burning a version number. The sibling project already solved this with a manual TestPyPI target.

**The pinned action versions are stale.** They were written against `actions/checkout@v4`,
`upload-artifact@v4` and `setup-uv@v5`; current are v7, v7 and v10, with `download-artifact` at
v8. A stale major is a build that breaks on someone else's deprecation schedule, not ours.

**Testing and publishing are one file with one trigger set.** Push, pull request, and release all
run the same workflow, so the release path shares its identity with the everyday one and neither
is named for what it does.

## What changes

Two workflows at the repository root, since GitHub reads them nowhere else, both running in
`code/` where the package lives.

### `ci.yml` — every push and pull request

The matrix, lint, type check, tests, and the check that the CLI works with no extras installed.
No publishing, no artifacts to promote.

### `publish.yml` — releases, and rehearsals

Runs the same matrix first, because publishing untested code is the failure this whole gate
exists to prevent. Then builds, then uploads.

- On a **published GitHub release**: upload to PyPI. Gated, as now, on the git tag matching the
  version in `pyproject.toml` and on the bundled `SKILL.md` being present in the wheel.
- On **manual dispatch**: a `target` choice of `testpypi` (the default) or `pypi`, so the whole
  pipeline can be rehearsed against TestPyPI before a version number is spent. When no TestPyPI
  token is configured, the run still builds and checks the artifacts and says why it skipped the
  upload, rather than failing.

Trusted Publishing stays the preference, with `id-token: write` for PEP 740 attestations and a
token fallback documented in place.

## Also

Run `ruff` with a cold cache in CI. A stale local cache reported a clean tree while a real lint
error sat in `tests/test_compare.py`; the error only appeared on a machine that had never linted
the file. CI is always that machine, so it would have failed there first — but the local command
should not have lied either.

## Documentation to update

- `system/tech-stack.md` — the CI/Release section describes one workflow; it becomes two, with
  the rehearsal path and the cold-cache rule.

## Agent Notes

Pin action majors to what is current and say so in a comment, so the next reader knows the pins
were checked rather than copied.
