---
title: "The skill a smaller model can follow"
status: applied
author: "bruno.fortunato@applica.guru"
created-at: "2026-09-10T00:00:00.000Z"
---

# The skill a smaller model can follow

## Why

CR-014 gave the skill a spine and CR-018 gave it the failure half, and both were written for a
reader that holds four hundred lines of argument at once and reasons by analogy. That reader is a
frontier model.

The skill now has to work for a 27B running on the same desk — Qwen, Gemma, whatever is local and
cheap. That reader fails on different things, and it fails quietly: it does not say "I did not
follow the argument", it emits a plausible command with a wrong flag.

Two defects. Only one of them is about length.

### `--use` asks the agent to know something it cannot see

The skill says it once, flatly:

> Always pass `--use <profile>` unless a default profile is configured.

The condition is invisible from where the agent stands. No `windows`, `tree` or action result
mentions whether `default-profile` is set; resolving it costs a `config show` that nothing tells
the agent to run; and the answer is the same for the entire session, because it is a fact about
the machine, settled once by whoever installed the tool.

The examples then disagree with each other. Five of the thirty-one shell examples carry
`--use laptop` or `--use staging`; the other twenty-six carry nothing. A model that generalises
from prose reads that as *when relevant*. A model that copies the nearest example reads it as
*sometimes* — and the failure that produces is not a missing flag but **an invented one**. On a
machine whose profile is called anything else, `--use laptop` warns
`profile 'laptop' is not defined in any config file` and then refuses with `no profile selected`:
two lines of error for a decision the agent should never have been handed.

A profile names which machine and which backend. Nothing the agent can observe distinguishes
`laptop` from `staging`, so it has no information with which to choose, and offering it the choice
is the defect. The flag belongs to the person who set the tool up, and it is already theirs:
`config init` writes `default-profile`, and `USE_COMPUTER_DEFAULT_PROFILE` preconfigures a harness
without touching a file.

### The shape of the document

Four hundred and eighty-two lines, and the good parts are prose: a table of what each way of
knowing is blind to, a ladder of rungs, a section on what a result is worth. It is argued, because
the thing it is teaching is a judgement and a judgement cannot be tabulated.

A smaller model reads that and extracts the command strings. The prose — which is to say
everything CR-014 and CR-018 added — does not survive the trip. What reaches the tool is a
screenshot-first, coordinate-first session, which is exactly the behaviour the skill was rewritten
twice to prevent.

The content is not the problem. **The order is.** An agent acts on what it reads first, and what
it reads first is currently a comparison table.

## What changes

### The skill stops saying `--use`

Every example drops it, and the sentence at the top goes. `--use` keeps existing — `--help`
declares it, a human with two machines needs it, and a CI job with several targets needs it — it
simply leaves the document written for a reader who cannot choose a value for it.

### Exactly one profile is the profile

Profile selection gains a last step, after `--use`, the environment, and `default-profile` in
every config layer have all come up empty: **if the configuration defines exactly one profile,
that is the profile.** There is nothing to disambiguate, so there is nothing to ask.

This does not grant anything. `allow-local` remains a separate opt-in, so a lone `local` profile
that has not opted in is auto-selected and still refuses — the refusal that matters is untouched.

`config show` must attribute the choice like any other resolved value, naming the layer it came
from. A profile selected by counting is fine; a profile selected invisibly is the kind of thing
that is discovered at the worst moment.

**The cost, stated out loud:** the day a second profile is added, bare commands that worked
yesterday become ambiguous. That is the right trade — one machine is the common case and two
machines means somebody is paying attention — but it is a behaviour change, and it is why the next
section matters.

### A refusal that names one command

Today the refusal offers a menu:

> no profile selected: pass `--use <profile>`, or set `default-profile` in
> `.use-computer/config.toml`, or set `USE_COMPUTER_DEFAULT_PROFILE`.

Three alternatives is a question, and the agent will answer it by guessing a profile name. The
message must branch on what is actually true and give **one** instruction:

- **No configuration at all** — the machine was never set up. Name `use-computer config init` and
  nothing else.
- **Several profiles, none marked default** — the tool cannot pick and neither can the agent. List
  the profile names that exist and say that `default-profile` has to be set. Listing them is not
  an invitation to choose one at random; it is what the person reading the transcript needs.

The skill carries one line about this, in the errors section: if the tool says the machine is not
configured, **stop and tell the user**. Do not guess a profile name, and do not run `config init`
on somebody's machine to get past an error.

### The skill leads with a procedure

The first thing in the document, before any table, is the whole tool as a numbered sequence a
model can execute without reading further:

1. `use-computer windows` — what is open, and the `--window` value for everything below.
2. `use-computer activate --window "X"` — bring it forward.
3. `use-computer tree --window "X"` — roles, names, ids, boxes.
4. Act by name: `click`, `focus`, `set-value`, `select`, `toggle`, `expand`.
5. `use-computer tree --window "X"` again — confirm by re-reading.
6. Only when the tree cannot see the thing: `screenshot --of <id>`, then a coordinate.

Six lines. Everything already in the skill stays and follows it, in the order it is needed:
the two ways of knowing, what a result is worth, the ladder, what is abbreviated, the errors.
Nothing argued is deleted — a frontier model reading to the end must find the same guidance it
finds today.

What is deleted is repetition. Verification is currently discussed in four places; the reader
this change is for pays for each one and learns from none of them.

## What does not change

- **`--use` itself.** The flag, its precedence, and every layer of the resolution stack.
- **`allow-local`.** A profile is selected for the agent; the local backend is still enabled only
  by the user.
- **The judgement.** Everything CR-014 and CR-018 put in the skill is still in the skill.
- **The direction of the truth test.** It asserts that what the skill names exists, not that it
  names everything. Removing five `--use` occurrences must not make it demand their return.

## Rejected: splitting the skill in two

The obvious move is `SKILL.md` for the procedure and a sibling `reference.md` for the argument,
which is how progressive disclosure is normally done and how this repository's own `sdd` skill is
laid out.

It is wrong here, for the reader this change is for. Progressive disclosure works when the reader
notices it is under-informed and goes and reads the second file. A smaller model does not do that:
it takes what is in front of it and acts. Splitting would put the judgement material behind a
door that the only audience who needs it never opens, and hand the frontier model an extra read
for material it was already getting.

It also costs more than it looks: the installer copies a single file, and `install`, `update`,
`remove` and `status` would all have to become directory operations with the ownership marker
still governing what may be deleted.

Ordering and cutting achieve the same thing with none of that.

## Agent Notes

- Bump `x-skill-version`. An agent with the old copy installed must see `outdated`.
- `test_skill_is_true` reads the bundled text and checks every flag and command it names against
  the CLI. Dropping `--use` from the skill is invisible to it — as it should be — but the six-step
  procedure introduces command and flag mentions that must all resolve.
- The auto-selection belongs in `_resolve`, next to the `default-profile` search, not in
  `ResolvedConfig.profile`. The property reports what resolution decided; it does not decide.
- The refusal is one message today. It becomes two, and each needs its own test: no config, and
  several profiles with no default. The single-profile path is the one that must now *not* raise.
- Counting profiles means counting across the project config and the global config together. A
  project file with one profile and a global file with another is two, not one.
