---
title: "windows lists only the frontmost application on macOS"
status: resolved
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-08T00:00:00.000Z"
---

# `windows` lists only the frontmost application on macOS

## What happens

A Mac with a terminal, a browser, a chat client and two other applications open, `use-computer
windows` run from the terminal:

```
id   app       role     title                                     pid  box              active
0/0  Terminal  helptag                                                 969,122 243x33
0/1  Terminal  window   use-computer — ◑ …                              356,56 1308x880  *
```

Two entries, both the terminal that ran the command. The window server, asked at the same moment,
had three ordinary windows on screen belonging to three different applications, and the
accessibility API answered for all of them when asked per process:

```
pid=642   'Terminal'         'use-computer — ◑ …'
pid=59756 'MongoDB Compass'  'MongoDB Compass'
pid=56134 'ChatGPT'          'ChatGPT'
```

`pid` is empty in every row as well, and the column is documented.

## Why

`ax.py` reaches the tree through `AXUIElementCreateSystemWide` → `AXFocusedApplication`, and that
is the whole of the enumeration: one application, the one in front. The provider says so, and
calls it a stated limitation:

```python
"""The windows of the frontmost application.

Not every application's: the accessibility API has no way to enumerate processes, and
the window-server list that would (`CGWindowListCopyWindowInfo`) is a different framework
and a dependency this does not carry. Said plainly here and in the docs rather than
quietly returning less than the other platforms do.
"""
```

Two halves of that are wrong.

**It is not said in the docs.** `ui-tree.md` documents `windows` as "what is open?" and shows two
applications in its own example; `interfaces.md` documents the same list. Nothing anywhere says
macOS answers for one application. The comment claiming otherwise is the only place it appears,
which is the worst place for it to be.

**`CGWindowListCopyWindowInfo` is not the only way out, and would have been the wrong one.** It
carries no AX element, so an id from it could not be handed back to `tree` or `activate`; and
`kCGWindowName` is `nil` without Screen Recording, so a listing would silently lose every title
on a machine that has granted Accessibility and nothing else. `NSWorkspace.runningApplications`
names the processes with no new permission and no new dependency — pyobjc-framework-Cocoa is
already a dependency of pyobjc-framework-ApplicationServices, which the `tree` extra installs —
and each pid turns into an AX element the rest of the provider already knows how to walk.

## Why it matters

`windows` is the first call the skill tells an agent to make, and it is the call that yields the
`--window` value every later one needs:

> Make this call first: it gives you the `--window` value everything else needs, and tells you
> which window `focused` will resolve to.

On macOS it answers with the terminal the agent is running in. An agent asked to act in the
browser reads that list, concludes the browser is not open, and either gives up or falls back to
blind coordinates — on a desktop where the tree could have described the window exactly.

`tree --window all` has the same blind spot for the same reason. The docs advertise it as "every
window, shallow"; it read the frontmost application.

## Also, once every application is asked

`kAXErrorAPIDisabled` is not only the session's answer, it is a *process's* answer too: measured
on this desktop, `ChatGPTHelper` returns it for `AXWindows` while the Accessibility grant is
plainly in place. `_attr` translated that code straight into `PermissionDeniedError`, so with
every application now asked, one helper process turned the whole listing into "you have
accessibility switched off". The code means what it says only when it is our own process that is
untrusted, and `AXIsProcessTrusted` is what actually answers that.

## Expected

- `windows` lists every application's windows, with the `app` and `pid` the other two platforms
  report, and an id that `tree --window ID` resolves back to the same window.
- At most one window carries `active`, and it is the focused window of the application the window
  server says is in front — the single decision `--window focused` resolves to.
- One application that will not answer costs its own windows and never the list, and no single
  application can report a permission failure on the session's behalf.
- `tree --window all` reads every application, as it says it does.
