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
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer
from rich.console import Console

from use_computer.actions import (
    Action,
    ActionListAdapter,
    ClickAction,
    DoubleClickAction,
    DragAction,
    KeyAction,
    MouseButton,
    MoveAction,
    RightClickAction,
    ScreenshotAction,
    ScrollAction,
    ScrollDirection,
    TypeAction,
)
from use_computer.config import ResolvedConfig
from use_computer.config import load as load_config
from use_computer.coordinates import CoordinateSpace
from use_computer.errors import UseComputerError
from use_computer.runner import Session, as_json
from use_computer.skill import Scope
from use_computer.skill import install as skill_install
from use_computer.skill import remove as skill_remove
from use_computer.skill import status as skill_status
from use_computer.skill import update as skill_update

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
    use: UseOption = None,
    space: SpaceOption = None,
    delay: DelayOption = None,
    dry_run: DryRunOption = False,
    verify: VerifyOption = False,
    verbose: VerboseOption = 0,
) -> None:
    """Click, at a coordinate or where the pointer already is."""
    config = _config(use, space=space, delay=delay, dry_run=dry_run, verify=verify, verbose=verbose)
    _run([ClickAction(x=x, y=y, space=space, button=button)], config, verbose)


@app.command("double-click")
def double_click(
    x: XOption = None,
    y: YOption = None,
    use: UseOption = None,
    space: SpaceOption = None,
    delay: DelayOption = None,
    dry_run: DryRunOption = False,
    verify: VerifyOption = False,
    verbose: VerboseOption = 0,
) -> None:
    """Double-click."""
    config = _config(use, space=space, delay=delay, dry_run=dry_run, verify=verify, verbose=verbose)
    _run([DoubleClickAction(x=x, y=y, space=space)], config, verbose)


@app.command("right-click")
def right_click(
    x: XOption = None,
    y: YOption = None,
    use: UseOption = None,
    space: SpaceOption = None,
    delay: DelayOption = None,
    dry_run: DryRunOption = False,
    verify: VerifyOption = False,
    verbose: VerboseOption = 0,
) -> None:
    """Click with the secondary button."""
    config = _config(use, space=space, delay=delay, dry_run=dry_run, verify=verify, verbose=verbose)
    _run([RightClickAction(x=x, y=y, space=space)], config, verbose)


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
    use: UseOption = None,
    space: SpaceOption = None,
    delay: DelayOption = None,
    dry_run: DryRunOption = False,
    verify: VerifyOption = False,
    verbose: VerboseOption = 0,
) -> None:
    """Scroll."""
    config = _config(use, space=space, delay=delay, dry_run=dry_run, verify=verify, verbose=verbose)
    _run([ScrollAction(amount=amount, direction=direction, x=x, y=y, space=space)], config, verbose)


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
    out: Annotated[Path | None, typer.Option("--out", help="Write the PNG here.")] = None,
    base64: Annotated[bool, typer.Option("--base64", help="Include the PNG in the JSON.")] = False,
    use: UseOption = None,
    verbose: VerboseOption = 0,
) -> None:
    """Capture the current screen."""
    config = _config(use, verbose=verbose)
    _run([ScreenshotAction(out=out, base64=base64)], config, verbose)


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
