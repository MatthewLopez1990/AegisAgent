from __future__ import annotations

import argparse
import re
from typing import Any


SUPPORTED_SHELLS = ("bash", "zsh", "fish")
_PROGRAM_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def build_completion_script(parser: argparse.ArgumentParser, shell: str, *, program: str = "aegis") -> str:
    if not _PROGRAM_NAME_RE.fullmatch(program):
        raise ValueError("completion program must contain only letters, numbers, dot, underscore, or dash")
    catalog = _completion_catalog(parser)
    if shell == "bash":
        return _bash_completion_script(catalog, program)
    if shell == "zsh":
        return _zsh_completion_script(catalog, program)
    if shell == "fish":
        return _fish_completion_script(catalog, program)
    raise ValueError(f"unsupported shell: {shell}")


def _completion_catalog(parser: argparse.ArgumentParser) -> dict[str, dict[str, Any]]:
    root_choices = _subparser_choices(parser)
    catalog: dict[str, dict[str, Any]] = {
        "__root__": {
            "commands": tuple(sorted(root_choices)),
            "options": tuple(sorted(_parser_options(parser))),
            "help": parser.description or "",
        }
    }
    for command, subparser in sorted(root_choices.items()):
        choices = {*_subparser_choices(subparser), *_parser_positional_choices(subparser)}
        catalog[command] = {
            "commands": tuple(sorted(choices)),
            "options": tuple(sorted(_parser_options(subparser))),
            "help": subparser.description or "",
        }
    return catalog


def _subparser_choices(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:  # noqa: SLF001 - argparse has no public parser catalog.
        if isinstance(action, argparse._SubParsersAction):  # type: ignore[attr-defined]
            return {name: choice for name, choice in action.choices.items() if isinstance(choice, argparse.ArgumentParser)}
    return {}


def _parser_positional_choices(parser: argparse.ArgumentParser) -> tuple[str, ...]:
    choices: list[str] = []
    for action in parser._actions:  # noqa: SLF001 - argparse exposes action metadata here.
        if action.option_strings:
            continue
        if isinstance(action.choices, (tuple, list, set)):
            choices.extend(str(choice) for choice in action.choices)
    return tuple(choices)


def _parser_options(parser: argparse.ArgumentParser) -> tuple[str, ...]:
    options: list[str] = []
    for action in parser._actions:  # noqa: SLF001 - argparse exposes option strings here.
        for option in action.option_strings:
            if option not in {"-h", "--help"}:
                options.append(option)
    return tuple(options)


def _shell_words(values: tuple[str, ...]) -> str:
    return " ".join(values)


def _single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _safe_function_name(program: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", program)


def _bash_completion_script(catalog: dict[str, dict[str, Any]], program: str) -> str:
    function_name = f"_{_safe_function_name(program)}"
    root_commands = _shell_words(catalog["__root__"]["commands"])
    root_options = _shell_words(catalog["__root__"]["options"])
    cases = []
    for command, entry in sorted((key, value) for key, value in catalog.items() if key != "__root__"):
        choices = _shell_words(tuple(sorted((*entry["commands"], *entry["options"]))))
        cases.append(f"    {command}) opts=\"{choices}\" ;;")
    case_body = "\n".join(cases)
    return "\n".join(
        [
            f"# AegisAgent completion for {program}",
            f"{function_name}() {{",
            "  local cur cmd opts",
            "  COMPREPLY=()",
            "  cur=\"${COMP_WORDS[COMP_CWORD]}\"",
            "  cmd=\"${COMP_WORDS[1]}\"",
            "  case \"$cmd\" in",
            case_body,
            f"    *) opts=\"{root_commands} {root_options}\" ;;",
            "  esac",
            "  COMPREPLY=( $(compgen -W \"$opts\" -- \"$cur\") )",
            "  return 0",
            "}",
            f"complete -F {function_name} {program}",
            "",
        ]
    )


def _zsh_completion_script(catalog: dict[str, dict[str, Any]], program: str) -> str:
    function_name = f"_{_safe_function_name(program)}"
    root_entries = " ".join(_single_quote(f"{command}:{catalog[command]['help']}") for command in catalog["__root__"]["commands"])
    root_options = " ".join(_single_quote(option) for option in catalog["__root__"]["options"])
    cases = []
    for command, entry in sorted((key, value) for key, value in catalog.items() if key != "__root__"):
        choices = " ".join(_single_quote(value) for value in tuple(sorted((*entry["commands"], *entry["options"]))))
        cases.append(f"    {command}) _describe 'options' ({choices}) ;;")
    case_body = "\n".join(cases)
    return "\n".join(
        [
            f"#compdef {program}",
            f"# AegisAgent completion for {program}",
            f"{function_name}() {{",
            "  local -a commands global_options",
            f"  commands=({root_entries})",
            f"  global_options=({root_options})",
            "  if (( CURRENT == 2 )); then",
            "    _describe 'commands' commands",
            "    _describe 'global options' global_options",
            "    return",
            "  fi",
            "  case ${words[2]} in",
            case_body,
            "  esac",
            "}",
            f"{function_name} \"$@\"",
            "",
        ]
    )


def _fish_completion_script(catalog: dict[str, dict[str, Any]], program: str) -> str:
    lines = [f"# AegisAgent completion for {program}"]
    for command in catalog["__root__"]["commands"]:
        lines.append(f"complete -c {program} -f -n '__fish_use_subcommand' -a {_single_quote(command)} -d {_single_quote(catalog[command]['help'])}")
    for option in catalog["__root__"]["options"]:
        lines.append(f"complete -c {program} -f -n '__fish_use_subcommand' -a {_single_quote(option)}")
    for command, entry in sorted((key, value) for key, value in catalog.items() if key != "__root__"):
        for value in tuple(sorted((*entry["commands"], *entry["options"]))):
            lines.append(f"complete -c {program} -f -n '__fish_seen_subcommand_from {command}' -a {_single_quote(value)}")
    lines.append("")
    return "\n".join(lines)
