---
title: "Vision"
status: synced
author: ""
last-modified: "2026-09-02T00:00:00.000Z"
version: "1.0"
---

# Vision

`use-computer` executes input on a screen for computer-use agents. It moves the mouse,
clicks, double-clicks, right-clicks, drags, scrolls, types text, presses key combinations,
and captures a screenshot of the current screen.

## The pair

`use-computer` is the **acting** half of a pair:

- **ui-locator** answers *where* — "where is the Invia button?" — and returns pixel coordinates.
- **use-computer** performs the click *there*.

Both are driven by another AI agent through a CLI that emits JSON on stdout and diagnostics on
stderr, with a Python API underneath. Neither tool decides what to do; they are precise
instruments for an agent that does.

## Three problems define the design

### 1. Coordinate spaces

A screenshot on a HiDPI display is larger than the space the operating system clicks in. Every
coordinate therefore carries the space it belongs to, and `use-computer` scales between
screenshot pixels and actuation units. When the ratio is unknown it **refuses to guess** — an
unhandled factor of two makes every click land in the wrong place, silently.

### 2. Setup cost

Opening a VNC connection dominates the cost of a single action. One run therefore accepts a
**batch** of actions and performs them over one connection.

### 3. Blind actuation

A click that lands on nothing looks exactly like a click that worked. An action can compare a
screenshot taken before and after and report whether the screen actually changed. That gives the
calling agent the feedback signal it needs to correct a stale coordinate instead of retrying
forever.

## Interchangeable backends

Two backends sit behind one interface:

- **local** — drives the display of the machine it runs on.
- **vnc** — drives a remote framebuffer over RFB.

A backend is chosen by a **named profile** in a project-local config file, so adding one is
configuration rather than code. Backends normalise a single key-name syntax, so one spelling of a
shortcut works on both, and each reports its own coordinate space and screen size.

## Safe by construction

Because it types real keystrokes and moves a real pointer:

- a **dry-run** mode resolves and logs actions without performing them;
- per-action delays and a typing rate that applications do not drop characters from;
- an **explicit opt-in** for the local backend;
- a clear error when the host denies the accessibility or screen-recording permission a backend
  needs, rather than silently doing nothing.

## Non-goals

- Deciding *what* to click — that is the calling agent's job, with ui-locator's help.
- Computer vision or element detection — that is ui-locator.
- Being a general automation framework or a test runner.

## Agent Notes

- The stack mirrors the ui-locator project; carry over its patterns and conventions rather than
  inventing new ones. See [system/architecture.md](../system/architecture.md) and
  [system/tech-stack.md](../system/tech-stack.md).
- All code lives under `code/` in a src layout at `code/src/use_computer`.
