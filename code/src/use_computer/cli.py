"""The command line the calling agent actually uses.

Two constraints here are not style choices:

* The default command is implemented by rewriting ``argv`` in the console-script entry point.
  It is never implemented by subclassing ``TyperGroup``: typer 0.27 stopped being click-based
  and that approach breaks silently.
* JSON is printed with plain ``json.dumps``. rich soft-wraps long strings and can emit a
  newline inside a JSON string, which corrupts the output an agent parses. rich is used only
  for human-facing text, and only on stderr.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer
from rich.console import Console

from use_computer.actions import (
    Action,
    ActionListAdapter,
    ClickAction,
    CollapseAction,
    DoubleClickAction,
    DragAction,
    ExpandAction,
    FocusAction,
    KeyAction,
    MouseButton,
    MoveAction,
    RightClickAction,
    ScreenshotAction,
    ScrollAction,
    ScrollDirection,
    SelectAction,
    SetValueAction,
    ShowMenuAction,
    ToggleAction,
    TreeAction,
    TypeAction,
)
from use_computer.config import ResolvedConfig, profile_env_var, write_initial_config
from use_computer.config import load as load_config
from use_computer.coordinates import CoordinateSpace
from use_computer.errors import UseComputerError
from use_computer.runner import Session, as_json
from use_computer.skill import Scope
from use_computer.skill import install as skill_install
from use_computer.skill import remove as skill_remove
from use_computer.skill import status as skill_status
from use_computer.skill import update as skill_update
from use_computer.tree import NodeSelector, TreeScope, Via


class BackendKind(str, Enum):
    """The backends `config init` can write a profile for."""

    LOCAL = "local"
    VNC = "vnc"


EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2

#: The command a bare invocation means. `use-computer actions.json` and `use-computer -` work.
DEFAULT_COMMAND = "batch"

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Execute input on a screen: move, click, drag, scroll, type, key, screenshot.",
)
skill_app = typer.Typer(no_args_is_help=True, help="Manage the bundled agent skill.")
config_app = typer.Typer(no_args_is_help=True, help="Inspect configuration.")
app.add_typer(skill_app, name="skill")
app.add_typer(config_app, name="config")

_err = Console(stderr=True, highlight=False, soft_wrap=True)


def _version_callback(value: bool) -> None:
    if value:
        from use_computer import __version__

        _emit({"version": __version__})
        raise typer.Exit(EXIT_OK)


@app.callback()
def _main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Print the version."
        ),
    ] = False,
) -> None:
    """Execute input on a screen: move, click, drag, scroll, type, key, screenshot."""

# --- shared options ----------------------------------------------------------------------------

UseOption = Annotated[
    str | None, typer.Option("--use", "-u", help="Named profile to use.", metavar="PROFILE")
]
XOption = Annotated[int | None, typer.Option("--x", help="X coordinate.")]
YOption = Annotated[int | None, typer.Option("--y", help="Y coordinate.")]
SpaceOption = Annotated[
    CoordinateSpace | None,
    typer.Option("--space", help="Coordinate space of the coordinates given."),
]
DelayOption = Annotated[
    float | None, typer.Option("--delay", help="Seconds to wait after each action.")
]
DryRunOption = Annotated[
    bool, typer.Option("--dry-run", help="Resolve and log without performing.")
]
VerifyOption = Annotated[
    bool, typer.Option("--verify", help="Compare the screen before and after each action.")
]
VerboseOption = Annotated[int, typer.Option("-v", count=True, help="Diagnostics on stderr.")]

# --- selector options ---------------------------------------------------------------------------
# An action names its target by coordinate or by element. These are the element half, shared by
# every command that accepts one, so an agent learns them once.

IdOption = Annotated[
    str | None, typer.Option("--id", help="Node id from `tree`. Checked against role and name.")
]
RoleOption = Annotated[str | None, typer.Option("--role", help="Match by role.")]
NameOption = Annotated[str | None, typer.Option("--name", help="Match by name (substring).")]
ExactOption = Annotated[bool, typer.Option("--exact", help="Match the name exactly.")]
NthOption = Annotated[
    int | None, typer.Option("--nth", help="Pick one of several candidates, 0-based.")
]
WindowOption = Annotated[
    str | None, typer.Option("--window", help="focused | all | TITLE | @PID.", metavar="SCOPE")
]
ViaOption = Annotated[Via, typer.Option("--via", help="Which rung to take.")]


def _build(
    kind: Any, selector: NodeSelector | None, via: Via, **fields: Any
) -> Action:
    """Construct an action from either a coordinate or an element -- never both.

    Choosing between them would be exactly the kind of silent reinterpretation this tool refuses
    to do with coordinate spaces, so a caller that gives both is told to pick one.
    """
    if selector is None:
        return kind(**fields)  # type: ignore[no-any-return]
    if fields.get("x") is not None or fields.get("y") is not None:
        _err.print(
            "[red]error:[/red] give a coordinate or a selector, not both -- "
            "the target is one thing or the other"
        )
        raise typer.Exit(EXIT_USAGE)
    fields = {k: v for k, v in fields.items() if k not in ("x", "y", "space")}
    return kind(selector=selector, via=via, **fields)  # type: ignore[no-any-return]


def _selector(
    node_id: str | None,
    role: str | None,
    name: str | None,
    exact: bool,
    nth: int | None,
    window: str | None,
) -> NodeSelector | None:
    """Build a selector from the flags, or None when the action was given a coordinate."""
    if node_id is None and role is None and name is None:
        return None
    return NodeSelector(
        node_id=node_id,
        role=role,
        name=name,
        exact=exact,
        nth=nth,
        window=TreeScope.parse(window),
    )


def _require_selector(
    node_id: str | None,
    role: str | None,
    name: str | None,
    exact: bool,
    nth: int | None,
    window: str | None,
) -> NodeSelector:
    """For the actions that only exist against an element."""
    selector = _selector(node_id, role, name, exact, nth, window)
    if selector is None:
        _err.print("[red]error:[/red] this action needs an element: pass --id, --role or --name")
        raise typer.Exit(EXIT_USAGE)
    return selector


def _emit(payload: Any) -> None:
    """stdout is JSON and nothing else."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _fail(exc: BaseException) -> NoReturn:
    _err.print(f"[red]error:[/red] {exc}")
    raise typer.Exit(EXIT_FAILURE)


def _config(
    profile: str | None,
    *,
    space: CoordinateSpace | None = None,
    delay: float | None = None,
    dry_run: bool = False,
    verify: bool = False,
    continue_on_error: bool = False,
    verbose: int = 0,
) -> ResolvedConfig:
    overrides: dict[str, Any] = {
        "space": space,
        "delay": delay,
        "dry_run": dry_run or None,
        "verify": verify or None,
        "continue_on_error": continue_on_error or None,
    }
    resolved = load_config(overrides, profile=profile)
    for warning in resolved.warnings:
        _err.print(f"[yellow]warning:[/yellow] {warning}")
    if verbose:
        _err.print(f"[dim]profile: {resolved.profile_name}[/dim]")
    return resolved


def _run(actions: Sequence[Action], config: ResolvedConfig, verbose: int = 0) -> NoReturn:
    try:
        session = Session.from_profile(config=config)
    except UseComputerError as exc:
        _fail(exc)
    except Exception as exc:  # a backend can fail to connect in its own vocabulary
        _fail(exc)
    try:
        result = session.run(actions)
    finally:
        session.close()

    _emit(as_json(result))
    if not result.ok:
        for item in result.results:
            if item.error is not None:
                _err.print(f"[red]{item.error.type}:[/red] {item.error.message}")
                for candidate in item.error.candidates or ():
                    name = f" {candidate.name!r}" if candidate.name else ""
                    _err.print(
                        f"  [dim]{candidate.id}[/dim] {candidate.role}{name} "
                        f"at ({candidate.box.x}, {candidate.box.y})"
                    )
                if item.error.screenshot is not None:
                    _err.print(f"  [dim]screenshot: {item.error.screenshot.path}[/dim]")
        raise typer.Exit(EXIT_FAILURE)
    if verbose:
        _err.print(f"[green]ok[/green] {len(result.results)} action(s)")
    raise typer.Exit(EXIT_OK)


# --- action commands ---------------------------------------------------------------------------


@app.command()
def move(
    x: Annotated[int, typer.Option("--x", help="X coordinate.")],
    y: Annotated[int, typer.Option("--y", help="Y coordinate.")],
    use: UseOption = None,
    space: SpaceOption = None,
    delay: DelayOption = None,
    dry_run: DryRunOption = False,
    verify: VerifyOption = False,
    verbose: VerboseOption = 0,
) -> None:
    """Move the pointer."""
    config = _config(use, space=space, delay=delay, dry_run=dry_run, verify=verify, verbose=verbose)
    _run([MoveAction(x=x, y=y, space=space)], config, verbose)


@app.command()
def click(
    x: XOption = None,
    y: YOption = None,
    button: Annotated[MouseButton, typer.Option("--button")] = MouseButton.LEFT,
    id: IdOption = None,
    role: RoleOption = None,
    name: NameOption = None,
    exact: ExactOption = False,
    nth: NthOption = None,
    window: WindowOption = None,
    via: ViaOption = Via.AUTO,
    use: UseOption = None,
    space: SpaceOption = None,
    delay: DelayOption = None,
    dry_run: DryRunOption = False,
    verify: VerifyOption = False,
    verbose: VerboseOption = 0,
) -> None:
    """Click an element, a coordinate, or where the pointer already is."""
    config = _config(use, space=space, delay=delay, dry_run=dry_run, verify=verify, verbose=verbose)
    selector = _selector(id, role, name, exact, nth, window)
    _run(
        [_build(ClickAction, selector, via, x=x, y=y, space=space, button=button)],
        config,
        verbose,
    )


@app.command("double-click")
def double_click(
    x: XOption = None,
    y: YOption = None,
    id: IdOption = None,
    role: RoleOption = None,
    name: NameOption = None,
    exact: ExactOption = False,
    nth: NthOption = None,
    window: WindowOption = None,
    via: ViaOption = Via.AUTO,
    use: UseOption = None,
    space: SpaceOption = None,
    delay: DelayOption = None,
    dry_run: DryRunOption = False,
    verify: VerifyOption = False,
    verbose: VerboseOption = 0,
) -> None:
    """Double-click an element or a coordinate."""
    config = _config(use, space=space, delay=delay, dry_run=dry_run, verify=verify, verbose=verbose)
    selector = _selector(id, role, name, exact, nth, window)
    _run([_build(DoubleClickAction, selector, via, x=x, y=y, space=space)], config, verbose)


@app.command("right-click")
def right_click(
    x: XOption = None,
    y: YOption = None,
    id: IdOption = None,
    role: RoleOption = None,
    name: NameOption = None,
    exact: ExactOption = False,
    nth: NthOption = None,
    window: WindowOption = None,
    via: ViaOption = Via.AUTO,
    use: UseOption = None,
    space: SpaceOption = None,
    delay: DelayOption = None,
    dry_run: DryRunOption = False,
    verify: VerifyOption = False,
    verbose: VerboseOption = 0,
) -> None:
    """Click an element or a coordinate with the secondary button."""
    config = _config(use, space=space, delay=delay, dry_run=dry_run, verify=verify, verbose=verbose)
    selector = _selector(id, role, name, exact, nth, window)
    _run([_build(RightClickAction, selector, via, x=x, y=y, space=space)], config, verbose)


@app.command()
def drag(
    from_x: Annotated[int, typer.Option("--from-x")],
    from_y: Annotated[int, typer.Option("--from-y")],
    to_x: Annotated[int, typer.Option("--to-x")],
    to_y: Annotated[int, typer.Option("--to-y")],
    button: Annotated[MouseButton, typer.Option("--button")] = MouseButton.LEFT,
    use: UseOption = None,
    space: SpaceOption = None,
    delay: DelayOption = None,
    dry_run: DryRunOption = False,
    verify: VerifyOption = False,
    verbose: VerboseOption = 0,
) -> None:
    """Press, move, release."""
    config = _config(use, space=space, delay=delay, dry_run=dry_run, verify=verify, verbose=verbose)
    action = DragAction(
        from_x=from_x, from_y=from_y, to_x=to_x, to_y=to_y, space=space, button=button
    )
    _run([action], config, verbose)


@app.command()
def scroll(
    amount: Annotated[int, typer.Option("--amount")],
    direction: Annotated[ScrollDirection, typer.Option("--direction")] = ScrollDirection.DOWN,
    x: XOption = None,
    y: YOption = None,
    id: IdOption = None,
    role: RoleOption = None,
    name: NameOption = None,
    exact: ExactOption = False,
    nth: NthOption = None,
    window: WindowOption = None,
    via: ViaOption = Via.AUTO,
    use: UseOption = None,
    space: SpaceOption = None,
    delay: DelayOption = None,
    dry_run: DryRunOption = False,
    verify: VerifyOption = False,
    verbose: VerboseOption = 0,
) -> None:
    """Scroll, at an element or a coordinate."""
    config = _config(use, space=space, delay=delay, dry_run=dry_run, verify=verify, verbose=verbose)
    selector = _selector(id, role, name, exact, nth, window)
    _run(
        [
            _build(
                ScrollAction, selector, via, amount=amount, direction=direction, x=x, y=y,
                space=space,
            )
        ],
        config,
        verbose,
    )


@app.command("type")
def type_text(
    text: Annotated[str, typer.Option("--text")],
    rate: Annotated[
        float | None, typer.Option("--rate", help="Seconds between keystrokes.")
    ] = None,
    use: UseOption = None,
    delay: DelayOption = None,
    dry_run: DryRunOption = False,
    verify: VerifyOption = False,
    verbose: VerboseOption = 0,
) -> None:
    """Type literal text. For shortcuts use `key`."""
    config = _config(use, delay=delay, dry_run=dry_run, verify=verify, verbose=verbose)
    _run([TypeAction(text=text, rate=rate)], config, verbose)


@app.command()
def key(
    combo: Annotated[str, typer.Argument(help="A key combination, e.g. ctrl+shift+t.")],
    use: UseOption = None,
    delay: DelayOption = None,
    dry_run: DryRunOption = False,
    verify: VerifyOption = False,
    verbose: VerboseOption = 0,
) -> None:
    """Press a key combination."""
    config = _config(use, delay=delay, dry_run=dry_run, verify=verify, verbose=verbose)
    try:
        action = KeyAction(combo=combo)
    except Exception as exc:
        _err.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(EXIT_USAGE) from exc
    _run([action], config, verbose)


@app.command()
def screenshot(
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write the PNG here. Otherwise the screenshot directory."),
    ] = None,
    use: UseOption = None,
    verbose: VerboseOption = 0,
) -> None:
    """Capture the current screen to a file and report its path."""
    config = _config(use, verbose=verbose)
    _run([ScreenshotAction(out=out)], config, verbose)


# --- element commands ---------------------------------------------------------------------------


@app.command()
def tree(
    window: WindowOption = None,
    depth: Annotated[int | None, typer.Option("--depth", help="Maximum depth.")] = None,
    role: RoleOption = None,
    name: NameOption = None,
    of: Annotated[
        str | None, typer.Option("--of", help="Re-enter at a node id from an earlier tree.")
    ] = None,
    all: Annotated[bool, typer.Option("--all", help="No pruning and no budget.")] = False,
    out: Annotated[
        Path | None, typer.Option("--out", help="Write the tree JSON here and return its path.")
    ] = None,
    no_fallback: Annotated[
        bool, typer.Option("--no-fallback", help="Do not capture a screenshot when there is none.")
    ] = False,
    use: UseOption = None,
    verbose: VerboseOption = 0,
) -> None:
    """Read the accessibility tree of the focused window."""
    config = _config(use, verbose=verbose)
    _run(
        [
            TreeAction(
                window=TreeScope.parse(window),
                depth=depth,
                role=role,
                name=name,
                of=of,
                all=all,
                out=out,
                fallback=False if no_fallback else None,
            )
        ],
        config,
        verbose,
    )


def _element_command(kind: Any, help_text: str) -> Any:
    """Every element-only action takes the same flags; declaring them once keeps them the same."""

    def command(
        id: IdOption = None,
        role: RoleOption = None,
        name: NameOption = None,
        exact: ExactOption = False,
        nth: NthOption = None,
        window: WindowOption = None,
        use: UseOption = None,
        delay: DelayOption = None,
        dry_run: DryRunOption = False,
        verify: VerifyOption = False,
        verbose: VerboseOption = 0,
    ) -> None:
        config = _config(use, delay=delay, dry_run=dry_run, verify=verify, verbose=verbose)
        selector = _require_selector(id, role, name, exact, nth, window)
        _run([kind(selector=selector)], config, verbose)

    command.__doc__ = help_text
    command.__name__ = kind.__name__
    return command


@app.command("set-value")
def set_value(
    value: Annotated[str, typer.Option("--value", help="The text to assign.")],
    id: IdOption = None,
    role: RoleOption = None,
    name: NameOption = None,
    exact: ExactOption = False,
    nth: NthOption = None,
    window: WindowOption = None,
    use: UseOption = None,
    delay: DelayOption = None,
    dry_run: DryRunOption = False,
    verify: VerifyOption = False,
    verbose: VerboseOption = 0,
) -> None:
    """Assign a value atomically, without keystrokes.

    Not a faster `type`: this emits no key events, and some applications only validate on them.
    """
    config = _config(use, delay=delay, dry_run=dry_run, verify=verify, verbose=verbose)
    selector = _require_selector(id, role, name, exact, nth, window)
    _run([SetValueAction(selector=selector, value=value)], config, verbose)


app.command("focus")(_element_command(FocusAction, "Give keyboard focus to an element."))
app.command("toggle")(_element_command(ToggleAction, "Flip a checkbox, switch or toggle button."))
app.command("expand")(
    _element_command(ExpandAction, "Open a disclosure, combo box or tree item.")
)
app.command("collapse")(_element_command(CollapseAction, "Close one."))
app.command("select")(
    _element_command(SelectAction, "Select an item in a list, tab strip or menu.")
)
app.command("show-menu")(
    _element_command(ShowMenuAction, "Open an element's context menu through the platform.")
)


@app.command()
def batch(
    source: Annotated[str, typer.Argument(metavar="PATH|-", help="JSON array of actions, or -.")],
    continue_on_error: Annotated[
        bool, typer.Option("--continue-on-error", help="Run the rest after a failure.")
    ] = False,
    use: UseOption = None,
    space: SpaceOption = None,
    delay: DelayOption = None,
    dry_run: DryRunOption = False,
    verify: VerifyOption = False,
    verbose: VerboseOption = 0,
) -> None:
    """Run a batch of actions over one connection."""
    raw = sys.stdin.read() if source == "-" else _read_file(source)
    try:
        actions = ActionListAdapter.validate_json(raw)
    except Exception as exc:
        _err.print(f"[red]error:[/red] {source} is not a valid action list: {exc}")
        raise typer.Exit(EXIT_USAGE) from exc
    config = _config(
        use,
        space=space,
        delay=delay,
        dry_run=dry_run,
        verify=verify,
        continue_on_error=continue_on_error,
        verbose=verbose,
    )
    _run(actions, config, verbose)


def _read_file(source: str) -> str:
    path = Path(source)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        _err.print(f"[red]error:[/red] cannot read {source}: {exc}")
        raise typer.Exit(EXIT_USAGE) from exc


# --- config ------------------------------------------------------------------------------------


@config_app.command("init")
def config_init(
    backend: Annotated[
        BackendKind | None,
        typer.Option("--backend", help="Backend to configure. Given, nothing is asked."),
    ] = None,
    profile: Annotated[
        str | None, typer.Option("--profile", help="Profile name. Defaults to the backend name.")
    ] = None,
    host: Annotated[str | None, typer.Option("--host", help="VNC host.")] = None,
    port: Annotated[int, typer.Option("--port", help="VNC port.")] = 5900,
    allow_local: Annotated[
        bool, typer.Option("--allow-local", help="Opt in to driving this machine.")
    ] = False,
    dir: DirOption = None,
    no_probe: Annotated[
        bool, typer.Option("--no-probe", help="Skip opening the backend afterwards.")
    ] = False,
    force: Annotated[bool, typer.Option("--force", help="Replace an existing config.")] = False,
) -> None:
    """Write a config, then prove it works."""
    root = dir or Path.cwd()
    interactive = backend is None and _stdin_is_a_tty()

    if interactive:
        kind, profile_name, host, port, allow_local, password = _ask(profile, port)
    else:
        if backend is None:
            _err.print(
                "[red]error:[/red] no backend given and stdin is not a terminal. Pass "
                "--backend local|vnc (and --host for vnc, or --allow-local for local)."
            )
            raise typer.Exit(EXIT_USAGE)
        kind = backend
        profile_name = profile or kind.value
        password = None
        if kind is BackendKind.VNC and not host:
            _err.print("[red]error:[/red] --backend vnc needs --host.")
            raise typer.Exit(EXIT_USAGE)
        if kind is BackendKind.LOCAL and not allow_local:
            _err.print(
                "[red]error:[/red] the local backend moves this machine's pointer and types on "
                "its keyboard. Pass --allow-local to opt in."
            )
            raise typer.Exit(EXIT_USAGE)

    try:
        config_path, env_path = write_initial_config(
            root,
            profile_name,
            kind.value,
            host=host,
            port=port,
            allow_local=allow_local,
            password=password,
            force=force,
        )
    except UseComputerError as exc:
        _fail(exc)

    payload: dict[str, Any] = {
        "action": "init",
        "config-file": str(config_path),
        "env-file": str(env_path) if env_path else None,
        "profile": profile_name,
        "backend": kind.value,
        "probe": None,
    }

    if no_probe:
        _emit(payload)
        _report_next_steps(kind, profile_name, env_path is None)
        raise typer.Exit(EXIT_OK)

    probe = _probe(root, profile_name)
    payload["probe"] = probe
    _emit(payload)
    if not probe["ok"]:
        _err.print(f"[red]probe failed:[/red] {probe['error']}")
        _err.print(f"[dim]{config_path} was written; correct it and try again.[/dim]")
        raise typer.Exit(EXIT_FAILURE)
    _report_next_steps(kind, profile_name, env_path is None)
    raise typer.Exit(EXIT_OK)


def _ask(
    profile: str | None, port: int
) -> tuple[BackendKind, str, str | None, int, bool, str | None]:
    """The guided half. Every question goes to stderr; stdout stays JSON."""
    _err.print("[bold]use-computer setup[/bold]")
    kind = _prompt_backend()
    host: str | None = None
    password: str | None = None
    allow_local = False

    if kind is BackendKind.VNC:
        host = typer.prompt("VNC host", err=True)
        port = int(typer.prompt("VNC port", default=port, err=True))
        password = (
            typer.prompt(
                "VNC password (leave empty for none; it is written to .use-computer/.env)",
                default="",
                hide_input=True,
                show_default=False,
                err=True,
            )
            or None
        )
    else:
        # Asked out loud. An opt-in nobody was asked for is not an opt-in.
        _err.print(
            "[yellow]The local backend moves this machine's pointer and types on its "
            "keyboard.[/yellow]"
        )
        allow_local = typer.confirm("Enable it?", default=False, err=True)
        if not allow_local:
            _err.print("[dim]Aborted: a local profile without the opt-in cannot run.[/dim]")
            raise typer.Exit(EXIT_OK)

    name = profile or typer.prompt("Profile name", default=kind.value, err=True)
    return kind, name, host, port, allow_local, password


def _stdin_is_a_tty() -> bool:
    """Whether there is a human to ask. Indirect so it can be exercised in tests."""
    return sys.stdin.isatty()


def _prompt_backend() -> BackendKind:
    """Ask until the answer is one of the backends.

    Validated here rather than with click's Choice: click is typer's dependency, not ours, and
    importing someone else's transitive dependency is how it breaks when they drop it.
    """
    choices = [kind.value for kind in BackendKind]
    while True:
        answer = typer.prompt(
            "Backend: local drives this machine, vnc drives a remote framebuffer",
            default=BackendKind.LOCAL.value,
            err=True,
        ).strip().lower()
        if answer in choices:
            return BackendKind(answer)
        _err.print(f"[red]{answer!r} is not a backend.[/red] Choose one of: {', '.join(choices)}")


def _probe(root: Path, profile: str) -> dict[str, Any]:
    """Open the backend just configured and report what it sees.

    A scale that cannot be derived is the most expensive failure this tool has, so setup is
    where it should surface -- not the first click.
    """
    try:
        resolved = load_config(profile=profile, start=root)
        session = Session.from_profile(config=resolved)
    except Exception as exc:
        return {"ok": False, "screen": None, "error": f"{type(exc).__name__}: {exc}"}
    try:
        screen = session.screen
    except Exception as exc:
        return {"ok": False, "screen": None, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        session.close()
    if screen.scale is None:
        return {
            "ok": False,
            "screen": screen.model_dump(mode="json"),
            "error": (
                f"the backend reports {screen.width}x{screen.height} actuation units and "
                f"{screen.screenshot_width}x{screen.screenshot_height} screenshot pixels, from "
                "which no consistent scale can be derived. Set `scale` explicitly in the profile."
            ),
        }
    return {"ok": True, "screen": screen.model_dump(mode="json"), "error": None}


def _report_next_steps(kind: BackendKind, profile: str, needs_password: bool) -> None:
    if kind is BackendKind.VNC and needs_password:
        _err.print(
            f"[dim]If the server needs a password, set "
            f"{profile_env_var(profile, 'password')} or put it in .use-computer/.env[/dim]"
        )
    _err.print(f"[green]ready[/green] try: use-computer screenshot --use {profile}")


@config_app.command("show")
def config_show(use: UseOption = None) -> None:
    """Print every resolved value, the layer it came from, and the variable that overrides it."""
    try:
        resolved = _config(use)
    except UseComputerError as exc:
        _fail(exc)
    _emit(resolved.show())


# --- skill -------------------------------------------------------------------------------------

ScopeOption = Annotated[Scope, typer.Option("--scope", help="Where to install the skill.")]
DirOption = Annotated[
    Path | None, typer.Option("--dir", help="Skills directory, overriding the scope.")
]


@skill_app.command("install")
def skill_install_command(
    scope: ScopeOption = Scope.PROJECT,
    dir: DirOption = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite an existing copy.")] = False,
) -> None:
    """Install the bundled skill."""
    try:
        state = skill_install(scope, override=dir, force=force)
    except UseComputerError as exc:
        _fail(exc)
    _emit({"action": "install", **_skill_json(state)})


@skill_app.command("update")
def skill_update_command(scope: ScopeOption = Scope.PROJECT, dir: DirOption = None) -> None:
    """Refresh an installed skill from the bundled copy."""
    try:
        state = skill_update(scope, override=dir)
    except UseComputerError as exc:
        _fail(exc)
    _emit({"action": "update", **_skill_json(state)})


@skill_app.command("remove")
def skill_remove_command(scope: ScopeOption = Scope.PROJECT, dir: DirOption = None) -> None:
    """Remove an installed skill."""
    try:
        state = skill_remove(scope, override=dir)
    except UseComputerError as exc:
        _fail(exc)
    _emit({"action": "remove", **_skill_json(state)})


@skill_app.command("status")
def skill_status_command(scope: ScopeOption = Scope.PROJECT, dir: DirOption = None) -> None:
    """Report whether the skill is installed and current."""
    state = skill_status(scope, override=dir)
    _emit({"action": "status", **_skill_json(state)})


def _skill_json(state: Any) -> dict[str, Any]:
    return {
        "scope": state.scope.value,
        "path": str(state.path),
        "status": state.status,
        "installed": state.installed,
        "up-to-date": state.up_to_date,
    }


# --- entry point -------------------------------------------------------------------------------

#: Every name argv may start with. Anything else is an argument to the default command.
_COMMANDS = frozenset(
    {
        "move",
        "click",
        "double-click",
        "right-click",
        "drag",
        "scroll",
        "type",
        "key",
        "screenshot",
        "tree",
        "focus",
        "toggle",
        "expand",
        "collapse",
        "select",
        "set-value",
        "show-menu",
        "batch",
        "config",
        "skill",
    }
)


def apply_default_command(argv: list[str]) -> list[str]:
    """Insert the default command when argv starts with something that is not a command.

    This is why the entry point exists: it is the supported way to have a default command in
    typer, and it keeps working across the versions that changed how typer builds its group.
    """
    if len(argv) < 2:
        return argv
    first = argv[1]
    if first in _COMMANDS or first.startswith("-") and first != "-":
        return argv
    return [argv[0], DEFAULT_COMMAND, *argv[1:]]


def main() -> None:
    """Console-script entry point."""
    sys.argv = apply_default_command(sys.argv)
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
