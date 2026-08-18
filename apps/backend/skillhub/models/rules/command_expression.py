"""CLI command expression parsing, normalisation and matching.

The command library stores expressions as text because they are also shown to
users.  This module keeps the executable representation deliberately small:
literal tokens, captures, sequences, choices, optional groups and repeats are
enough for the editor and search API while remaining backwards compatible with
the existing ``commandTemplate`` field.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from skillhub.models.errors import InvariantError

_CAPTURE_RE = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_-]*)$")
_CAPTURE_REPEAT_RE = re.compile(r"^<(?P<name>[A-Za-z_][A-Za-z0-9_-]*)>&<(?P<minimum>[0-9]+)-(?P<maximum>[0-9]+)>$")
_CAPTURE_RANGE_RE = re.compile(r"^<(?P<minimum>[0-9]+)-(?P<maximum>[0-9]+)>$")
_PUNCTUATION = frozenset("[](){}|")
_QUOTED_TOKEN_PREFIX = "\x00"
MAX_COMMAND_TOKENS = 128


@dataclass(frozen=True, slots=True)
class ExpressionNode:
    kind: str
    value: str = ""
    quoted: bool = False
    children: tuple["ExpressionNode", ...] = ()
    name: str = ""
    value_type: str | None = None
    minimum: int = 1
    maximum: int | None = 1


@dataclass(frozen=True, slots=True)
class CommandExpression:
    source: str
    normalized: str
    root: ExpressionNode
    tokens: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CommandMatch:
    captures: dict[str, Any]
    score: int
    exact: bool
    partial: bool
    consumed_tokens: int
    normalized_expression: str
    ambiguous: bool = False
    alternatives: tuple[dict[str, Any], ...] = ()


def parse_command_expression(value: str | CommandExpression) -> CommandExpression:
    """Parse one command expression and return its canonical AST."""
    if isinstance(value, CommandExpression):
        return value
    if not isinstance(value, str) or not value.strip():
        raise InvariantError("Command expression cannot be blank.")
    tokens = tuple(_lex_expression(value))
    if not tokens:
        raise InvariantError("Command expression cannot be blank.")
    if len(tokens) > MAX_COMMAND_TOKENS:
        raise InvariantError(f"Command expression exceeds the {MAX_COMMAND_TOKENS}-token limit.")
    parser = _ExpressionParser(tokens)
    root = parser.parse()
    _validate_capture_paths(root)
    return CommandExpression(source=value, normalized=_render(root), root=root, tokens=tokens)


def normalize_command_expression(value: str | CommandExpression) -> str:
    """Return the stable representation used for equality and search."""
    return parse_command_expression(value).normalized


def match_command_expression(
    expression: str | CommandExpression,
    command: str | Sequence[str],
    *,
    partial: bool = False,
    prefix: bool = False,
) -> CommandMatch | None:
    """Match a command against an expression, including optional partial input."""
    parsed = parse_command_expression(expression)
    command_tokens = _command_tokens(command)
    if not command_tokens:
        return None
    if len(command_tokens) > MAX_COMMAND_TOKENS:
        raise InvariantError(f"Command input exceeds the {MAX_COMMAND_TOKENS}-token limit.")
    allow_partial = partial or prefix
    outcomes = _match_node(parsed.root, command_tokens, 0, {}, allow_partial=allow_partial)
    complete = [item for item in outcomes if item[0] == len(command_tokens)]
    if not complete:
        return None
    best = max(
        complete,
        key=lambda item: (item[2], -item[3], -item[4]),
    )
    consumed, captures, literal_score, capture_count, partial_literal = best
    ambiguous = len({_freeze_captures(item[1]) for item in complete}) > 1
    is_exact = consumed == len(command_tokens) and partial_literal == 0
    is_partial = not is_exact
    score = literal_score * 100 - capture_count * 3
    if is_exact:
        score += 10000
    elif prefix:
        score += 6000
    elif partial:
        score += 3000
    alternatives: list[dict[str, Any]] = []
    seen_alternatives: set[tuple[tuple[str, Any], ...]] = set()
    for item in sorted(complete, key=lambda value: (value[2], -value[3], -value[4]), reverse=True):
        frozen = _freeze_captures(item[1])
        if frozen in seen_alternatives:
            continue
        seen_alternatives.add(frozen)
        alternatives.append(dict(item[1]))
    return CommandMatch(
        captures=captures,
        score=score,
        exact=is_exact,
        partial=is_partial,
        consumed_tokens=consumed,
        normalized_expression=parsed.normalized,
        ambiguous=ambiguous,
        alternatives=tuple(alternatives),
    )


def next_command_tokens(
    expression: str | CommandExpression,
    command: str | Sequence[str],
    *,
    limit: int = 16,
) -> list[str]:
    """Return only tokens that can continue the entered command prefix.

    The old implementation sliced the flattened expression token list.  That
    exposed alternatives from branches which had already been ruled out (for
    example ``detail`` after the user selected ``brief``).  Candidate tokens
    are now tested against the parsed AST, so optional/choice/repeat groups
    contribute only reachable hints.
    """
    parsed = parse_command_expression(expression)
    query_tokens = _command_tokens(command)
    result: list[str] = []
    for path in _expression_paths(parsed.root):
        if not query_tokens:
            if path:
                _append_hint(result, path[0], limit)
            continue
        exact = True
        for index, actual in enumerate(query_tokens):
            if index >= len(path):
                exact = False
                break
            expected = path[index]
            if _hint_token_matches(actual, expected):
                continue
            exact = False
            if index == len(query_tokens) - 1 and not expected.startswith("<"):
                actual_value = _strip_outer_quotes(actual).casefold()
                expected_value = _strip_outer_quotes(expected).casefold()
                if actual_value and expected_value.startswith(actual_value):
                    _append_hint(result, expected, limit)
            break
        if exact and len(query_tokens) < len(path):
            _append_hint(result, path[len(query_tokens)], limit)
        if len(result) >= max(0, limit):
            break
    return result[: max(0, limit)]


_MAX_HINT_PATHS = 512


def _append_hint(result: list[str], value: str, limit: int) -> None:
    if value not in result and len(result) < max(0, limit):
        result.append(value)


def _hint_token_matches(actual: str, expected: str) -> bool:
    if expected.startswith("<"):
        return True
    return _strip_outer_quotes(actual).casefold() == _strip_outer_quotes(expected).casefold()


def _expression_paths(node: ExpressionNode) -> list[list[str]]:
    """Expand the finite expression choices used for completion hints."""
    if node.kind == "literal":
        return [[_render_literal(node.value, quoted=node.quoted)]]
    if node.kind == "capture":
        return [[_render(node)]]
    if node.kind in {"choice", "choice_repeat"}:
        if node.kind == "choice":
            paths: list[list[str]] = []
            for child in node.children:
                paths.extend(_expression_paths(child))
            return paths[:_MAX_HINT_PATHS]
        paths = []
        if node.minimum == 0:
            paths.append([])
        maximum = node.maximum if node.maximum is not None else len(node.children)
        for count in range(max(node.minimum, 1), maximum + 1):
            for indices in _ordered_combinations(len(node.children), count):
                variants = [[]]
                for index in indices:
                    variants = _join_paths(variants, _expression_paths(node.children[index]))
                paths.extend(variants)
                if len(paths) >= _MAX_HINT_PATHS:
                    return paths[:_MAX_HINT_PATHS]
        return paths
    if node.kind == "optional":
        return [[], *_expression_paths(node.children[0])][:_MAX_HINT_PATHS]
    if node.kind == "repeat":
        maximum = node.maximum if node.maximum is not None else node.minimum + 3
        paths: list[list[str]] = []
        for count in range(node.minimum, maximum + 1):
            variants = [[]]
            for _ in range(count):
                variants = _join_paths(variants, _expression_paths(node.children[0]))
            paths.extend(variants)
            if len(paths) >= _MAX_HINT_PATHS:
                return paths[:_MAX_HINT_PATHS]
        return paths
    if node.kind == "sequence":
        paths = [[]]
        for child in node.children:
            paths = _join_paths(paths, _expression_paths(child))
        return paths[:_MAX_HINT_PATHS]
    return [[]]


def _join_paths(left: Sequence[list[str]], right: Sequence[list[str]]) -> list[list[str]]:
    return [(*before, *after) for before in left for after in right][:_MAX_HINT_PATHS]


def _ordered_combinations(size: int, count: int) -> Iterable[tuple[int, ...]]:
    if count == 0:
        yield ()
        return
    for start in range(size - count + 1):
        for suffix in _ordered_combinations(size - start - 1, count - 1):
            yield (start, *(item + start + 1 for item in suffix))


def search_command_expressions(
    entries: Iterable[Any],
    query: str,
    *,
    limit: int | None = None,
    partial: bool = True,
    prefix: bool = True,
) -> list[dict[str, Any]]:
    """Match and deterministically rank command-library records."""
    result: list[dict[str, Any]] = []
    for entry in entries:
        expression = _entry_value(entry, "expression") or _entry_value(entry, "command_template")
        if not expression:
            continue
        try:
            match = match_command_expression(expression, query, partial=partial, prefix=prefix)
        except InvariantError:
            continue
        if match is None:
            continue
        row = _entry_mapping(entry)
        row["match"] = match
        row["score"] = match.score
        row["consumedTokens"] = match.consumed_tokens
        row["ambiguous"] = match.ambiguous
        result.append(row)
    result.sort(
        key=lambda item: (
            -int(item["score"]),
            -int(item.get("consumedTokens", 0)),
            0 if item.get("source") == "system" else 1,
            str(item.get("name", "")).casefold(),
            str(item.get("key", "")).casefold(),
            str(item.get("id", "")),
        )
    )
    return result if limit is None else result[: max(0, limit)]


def capture_catalog(expression: str | CommandExpression | ExpressionNode) -> dict[str, dict[str, Any]]:
    """Derive string input schemas from every possible expression path."""
    node = expression.root if isinstance(expression, CommandExpression) else expression
    if isinstance(node, str):
        node = parse_command_expression(node).root
    paths = _capture_path_maps(node)
    names = sorted({name for path in paths for name in path})
    return {
        name: {
            "type": "string",
            "repeated": any(path.get(name, False) for path in paths if name in path),
            "optional": any(name not in path for path in paths),
        }
        for name in names
    }


# Stable CLI-oriented aliases for callers that do not use the storage name.
parse_cli_expression = parse_command_expression
normalize_cli_expression = normalize_command_expression
match_cli_expression = match_command_expression


class _ExpressionParser:
    def __init__(self, tokens: Sequence[str]):
        self.tokens = tokens
        self.index = 0

    def parse(self) -> ExpressionNode:
        node = self._parse_sequence(set())
        if self.index != len(self.tokens):
            raise InvariantError(f"Unexpected command expression token: {self.tokens[self.index]}")
        return node

    def _parse_choice(self, closing: set[str]) -> ExpressionNode:
        alternatives = [self._parse_sequence(closing | {"|"})]
        while self._peek() == "|":
            self.index += 1
            alternatives.append(self._parse_sequence(closing | {"|"}))
        if any(not item.children and item.kind == "sequence" for item in alternatives):
            raise InvariantError("Command expression alternatives cannot be empty.")
        if len(alternatives) == 1:
            return alternatives[0]
        return ExpressionNode("choice", children=tuple(alternatives))

    def _parse_sequence(self, closing: set[str]) -> ExpressionNode:
        children: list[ExpressionNode] = []
        while self._peek() is not None and self._peek() not in closing:
            children.append(self._parse_atom())
        if not children:
            return ExpressionNode("sequence")
        if len(children) == 1:
            return children[0]
        return ExpressionNode("sequence", children=tuple(children))

    def _parse_atom(self) -> ExpressionNode:
        token = self._take()
        if token in {"[", "(", "{"}:
            close = {"[": "]", "(": ")", "{": "}"}[token]
            child = self._parse_choice({close})
            if self._peek() != close:
                raise InvariantError(f"Unclosed command expression group: {token}")
            self.index += 1
            if token == "{" and child.kind != "choice":
                raise InvariantError("Command expression choice groups require at least two alternatives.")
            node = child
            if token == "[":
                node = ExpressionNode("optional", children=(child,))
            return self._apply_repeat(node)
        if token in {"]", ")", "}"}:
            raise InvariantError(f"Unexpected command expression token: {token}")
        node = _token_node(token)
        if node.kind == "capture" and self._peek() == "&":
            range_token = self.tokens[self.index + 1] if self.index + 1 < len(self.tokens) else None
            repeated = _CAPTURE_RANGE_RE.fullmatch(range_token or "")
            if repeated is None:
                raise InvariantError("Command capture repetition range is invalid.")
            self.index += 2
            minimum, maximum = int(repeated.group("minimum")), int(repeated.group("maximum"))
            if minimum < 1 or minimum > maximum:
                raise InvariantError("Command capture repetition range is invalid.")
            node = ExpressionNode("capture", name=node.name, minimum=minimum, maximum=maximum)
        return self._apply_repeat(node)

    def _apply_repeat(self, node: ExpressionNode) -> ExpressionNode:
        suffix = self._peek()
        if suffix not in {"?", "*", "+", "..."}:
            return node
        self.index += 1
        if suffix == "?":
            return ExpressionNode("repeat", children=(node,), minimum=0, maximum=1)
        if suffix == "+":
            return ExpressionNode("repeat", children=(node,), minimum=1, maximum=None)
        if suffix == "*" and node.kind == "choice":
            return ExpressionNode("choice_repeat", children=node.children, minimum=1, maximum=len(node.children))
        if suffix == "*" and node.kind == "optional" and node.children[0].kind == "choice":
            # Both `{x|y}*` and `[x|y]*` select each branch at most once;
            # the latter additionally permits selecting no branch.
            choice = node.children[0]
            return ExpressionNode("choice_repeat", children=choice.children, minimum=0, maximum=len(choice.children))
        return ExpressionNode("repeat", children=(node,), minimum=0, maximum=None)

    def _peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _take(self) -> str:
        value = self._peek()
        if value is None:
            raise InvariantError("Unexpected end of command expression.")
        self.index += 1
        return value


def _token_node(token: str) -> ExpressionNode:
    if token.startswith(_QUOTED_TOKEN_PREFIX):
        return ExpressionNode("literal", value=token.removeprefix(_QUOTED_TOKEN_PREFIX), quoted=True)
    repeated = _CAPTURE_REPEAT_RE.fullmatch(token)
    if repeated:
        minimum, maximum = int(repeated.group("minimum")), int(repeated.group("maximum"))
        if minimum < 1 or minimum > maximum:
            raise InvariantError("Command capture repetition range is invalid.")
        return ExpressionNode("capture", name=repeated.group("name"), minimum=minimum, maximum=maximum)
    if token.startswith("<") and token.endswith(">"):
        match = _CAPTURE_RE.fullmatch(token[1:-1].strip())
        if match is None:
            raise InvariantError(f"Invalid command capture: {token}")
        return ExpressionNode("capture", name=match.group("name"))
    return ExpressionNode("literal", value=token)


def _lex_expression(value: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    quoted = False
    quoted_token = False
    index = 0
    while index < len(value):
        char = value[index]
        if quoted:
            if char == '"':
                quoted = False
            else:
                current.append(char)
        elif char == '"':
            quoted = True
            quoted_token = True
        elif char.isspace():
            if current:
                token = "".join(current)
                tokens.append(f"{_QUOTED_TOKEN_PREFIX}{token}" if quoted_token else token)
                current = []
                quoted_token = False
        elif char in _PUNCTUATION:
            if current:
                tokens.append("".join(current))
                current = []
            tokens.append(char)
        elif char == "." and value[index : index + 3] == "...":
            if current:
                tokens.append("".join(current))
                current = []
            tokens.append("...")
            index += 2
        elif char in {"?", "+", "*"}:
            if current:
                tokens.append("".join(current))
                current = []
            tokens.append(char)
        else:
            current.append(char)
        index += 1
    if quoted:
        raise InvariantError("Unclosed quote in command expression.")
    if current:
        token = "".join(current)
        tokens.append(f"{_QUOTED_TOKEN_PREFIX}{token}" if quoted_token else token)
    return tokens


def _command_tokens(command: str | Sequence[str]) -> list[str]:
    if isinstance(command, str):
        raw_tokens = _lex_command(command)
    else:
        raw_tokens = [str(item) for item in command]
    return raw_tokens


def _lex_command(value: str) -> list[str]:
    """Split an entered command while retaining quote characters for captures."""
    tokens: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for char in value.strip():
        if quote is not None:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            current.append(char)
        elif char.isspace():
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(char)
    if quote is not None:
        raise InvariantError("Unclosed quote in command input.")
    if current:
        tokens.append("".join(current))
    return tokens


def _strip_outer_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _freeze_captures(captures: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    def freeze(value: Any) -> Any:
        if isinstance(value, Mapping):
            return tuple(sorted((str(key), freeze(item)) for key, item in value.items()))
        if isinstance(value, list):
            return tuple(freeze(item) for item in value)
        return value

    return tuple(sorted((str(name), freeze(value)) for name, value in captures.items()))


def _match_node(
    node: ExpressionNode,
    tokens: Sequence[str],
    index: int,
    captures: dict[str, Any],
    *,
    allow_partial: bool,
    memo: dict[tuple[ExpressionNode, int, tuple[tuple[str, Any], ...], bool], list[tuple[int, dict[str, Any], int, int, int]]] | None = None,
) -> list[tuple[int, dict[str, Any], int, int, int]]:
    """Memoize AST states so nested option groups stay bounded per query."""
    cache = memo if memo is not None else {}
    key = (node, index, _freeze_captures(captures), allow_partial)
    cached = cache.get(key)
    if cached is not None:
        return [(item[0], dict(item[1]), item[2], item[3], item[4]) for item in cached]
    outcomes = _match_node_uncached(node, tokens, index, captures, allow_partial=allow_partial, memo=cache)
    cache[key] = [(item[0], dict(item[1]), item[2], item[3], item[4]) for item in outcomes]
    return outcomes


def _match_node_uncached(
    node: ExpressionNode,
    tokens: Sequence[str],
    index: int,
    captures: dict[str, Any],
    *,
    allow_partial: bool,
    memo: dict[tuple[ExpressionNode, int, tuple[tuple[str, Any], ...], bool], list[tuple[int, dict[str, Any], int, int, int]]],
) -> list[tuple[int, dict[str, Any], int, int, int]]:
    if node.kind == "literal":
        if index >= len(tokens):
            if allow_partial:
                return [(index, captures, 0, 0, 1)]
            return []
        actual = tokens[index]
        actual_value = _strip_outer_quotes(actual)
        if actual_value.casefold() == node.value.casefold():
            return [(index + 1, captures, 10, 0, 0)]
        if allow_partial and node.value.casefold().startswith(actual_value.casefold()):
            return [(index + 1, captures, 4, 0, 1)]
        return []
    if node.kind == "capture":
        if index >= len(tokens):
            if allow_partial:
                return [(index, dict(captures), 0, 0, 1)]
            return []
        max_count = min(node.maximum or 1, len(tokens) - index)
        if max_count < node.minimum:
            return []
        outcomes = []
        for count in range(node.minimum, max_count + 1):
            updated = dict(captures)
            prior = updated.get(node.name)
            values = list(prior) if isinstance(prior, list) else ([] if prior is None else [prior])
            values.extend(tokens[index : index + count])
            repeated = node.maximum != 1 or node.minimum != 1
            updated[node.name] = values if repeated or count > 1 or prior is not None or isinstance(prior, list) else values[0]
            outcomes.append((index + count, updated, count, count, 0))
        return outcomes
    if node.kind == "sequence":
        outcomes = [(index, captures, 0, 0, 0)]
        for child in node.children:
            next_outcomes: list[tuple[int, dict[str, Any], int, int, int]] = []
            for child_index, child_captures, score, count, partial_count in outcomes:
                for result in _match_node(child, tokens, child_index, child_captures, allow_partial=allow_partial, memo=memo):
                    next_outcomes.append((result[0], result[1], score + result[2], count + result[3], partial_count + result[4]))
            outcomes = next_outcomes
            if not outcomes:
                break
        return outcomes
    if node.kind == "choice":
        choice_results: list[tuple[int, dict[str, Any], int, int, int]] = []
        for child in node.children:
            choice_results.extend(_match_node(child, tokens, index, dict(captures), allow_partial=allow_partial, memo=memo))
        return choice_results
    if node.kind == "optional":
        return [
            (index, dict(captures), 0, 0, 0),
            *_match_node(node.children[0], tokens, index, dict(captures), allow_partial=allow_partial, memo=memo),
        ]
    if node.kind == "repeat":
        repeat_results: list[tuple[int, dict[str, Any], int, int, int]] = []
        frontier = [(index, dict(captures), 0, 0, 0)]
        if node.minimum == 0:
            repeat_results.extend(frontier)
        for count in range(1, len(tokens) - index + 1):
            next_frontier: list[tuple[int, dict[str, Any], int, int, int]] = []
            for current in frontier:
                for item in _match_node(node.children[0], tokens, current[0], current[1], allow_partial=allow_partial, memo=memo):
                    if item[0] == current[0]:
                        continue
                    repeated_captures = _capture_names(node.children[0])
                    updated = dict(item[1])
                    for name in repeated_captures:
                        value = updated.get(name)
                        if value is not None and not isinstance(value, list):
                            updated[name] = [value]
                    next_frontier.append((item[0], updated, current[2] + item[2], current[3] + item[3], current[4] + item[4]))
            if not next_frontier:
                break
            frontier = next_frontier
            if count >= node.minimum:
                repeat_results.extend(frontier)
            if node.maximum is not None and count >= node.maximum:
                break
        return repeat_results
    if node.kind == "choice_repeat":
        results: list[tuple[int, dict[str, Any], int, int, int]] = []
        frontier: list[tuple[int, dict[str, Any], int, int, int, int, int]] = [
            (index, dict(captures), 0, 0, 0, -1, 0)
        ]
        if node.minimum == 0:
            results.append((index, dict(captures), 0, 0, 0))
        elif allow_partial and index == len(tokens):
            results.append((index, dict(captures), 0, 0, 1))
        while frontier:
            next_frontier: list[tuple[int, dict[str, Any], int, int, int, int, int]] = []
            seen_states: set[tuple[int, tuple[tuple[str, Any], ...], int, int]] = set()
            for current_index, current_captures, score, capture_count, partial_count, last_branch, selected_count in frontier:
                if node.maximum is not None and selected_count >= node.maximum:
                    continue
                for branch_index in range(last_branch + 1, len(node.children)):
                    child = node.children[branch_index]
                    for item in _match_node(child, tokens, current_index, current_captures, allow_partial=allow_partial, memo=memo):
                        if item[0] == current_index:
                            continue
                        next_selected_count = selected_count + 1
                        state_key = (item[0], _freeze_captures(item[1]), branch_index, next_selected_count)
                        if state_key in seen_states:
                            continue
                        seen_states.add(state_key)
                        next_frontier.append(
                            (
                                item[0],
                                item[1],
                                score + item[2],
                                capture_count + item[3],
                                partial_count + item[4],
                                branch_index,
                                next_selected_count,
                            )
                        )
            if not next_frontier:
                break
            for item in next_frontier:
                if item[6] >= node.minimum:
                    results.append(item[:5])
            frontier = next_frontier
        return results
    raise InvariantError(f"Unsupported command expression node: {node.kind}")


def _validate_capture_paths(node: ExpressionNode) -> None:
    """Reject duplicate captures on one path while allowing choice reuse."""
    _capture_path_maps(node)


def _capture_names(node: ExpressionNode) -> set[str]:
    """Return capture names below a repeated node for stable array results."""
    if node.kind == "capture":
        return {node.name}
    names: set[str] = set()
    for child in node.children:
        names.update(_capture_names(child))
    return names


def _capture_path_maps(node: ExpressionNode) -> list[dict[str, bool]]:
    if node.kind == "capture":
        return [{node.name: node.maximum != 1 or node.minimum != 1}]
    if node.kind == "literal":
        return [{}]
    if node.kind == "choice":
        paths: list[dict[str, bool]] = []
        for child in node.children:
            paths.extend(_capture_path_maps(child))
        return _dedupe_capture_paths(paths)
    if node.kind == "choice_repeat":
        paths: list[dict[str, bool]] = []
        child_paths: list[dict[str, bool]] = []
        for child in node.children:
            child_paths.extend(_capture_path_maps(child))
        # A repeated choice can select two branches that expose the same
        # capture name.  That name is therefore an array even when each
        # individual branch contains a scalar capture.
        branch_counts: dict[str, int] = {}
        for path in child_paths:
            for name in path:
                branch_counts[name] = branch_counts.get(name, 0) + 1
        repeated_group = node.maximum is None or node.maximum > 1
        for path in child_paths:
            paths.append(
                {
                    name: bool(repeated) or (repeated_group and branch_counts.get(name, 0) > 1)
                    for name, repeated in path.items()
                }
            )
        if node.minimum == 0:
            paths.append({})
        return _dedupe_capture_paths(paths)
    if node.kind == "optional":
        return [{}, *_capture_path_maps(node.children[0])]
    if node.kind == "repeat":
        child_paths = _capture_path_maps(node.children[0])
        repeated = node.maximum is None or node.maximum > 1
        paths = [
            {name: (repeated or repeated_value) for name, repeated_value in path.items()}
            for path in child_paths
        ]
        if node.minimum == 0:
            paths.append({})
        return _dedupe_capture_paths(paths)
    if node.kind == "sequence":
        paths = [{}]
        for child in node.children:
            child_paths = _capture_path_maps(child)
            combined: list[dict[str, bool]] = []
            for left in paths:
                for right in child_paths:
                    overlap = set(left) & set(right)
                    if any(not left[name] and not right[name] for name in overlap):
                        names = ", ".join(sorted(overlap))
                        raise InvariantError(f"Capture appears more than once on one command path: {names}")
                    merged = dict(left)
                    for name, repeated in right.items():
                        merged[name] = merged.get(name, False) or repeated
                    combined.append(merged)
            paths = combined
        return _dedupe_capture_paths(paths)
    return [{}]


def _dedupe_capture_paths(paths: Iterable[dict[str, bool]]) -> list[dict[str, bool]]:
    result: list[dict[str, bool]] = []
    seen: set[tuple[tuple[str, bool], ...]] = set()
    for path in paths:
        key = tuple(sorted((str(name), bool(repeated)) for name, repeated in path.items()))
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(path))
    return result or [{}]


def _render(node: ExpressionNode) -> str:
    if node.kind == "literal":
        return _render_literal(node.value, quoted=node.quoted)
    if node.kind == "capture":
        suffix = f":{node.value_type}" if node.value_type else ""
        repeat = f"&<{node.minimum}-{node.maximum}>" if node.maximum not in {None, 1} or node.minimum != 1 else ""
        return f"<{node.name}{suffix}>{repeat}"
    if node.kind == "sequence":
        return " ".join(_render(item) for item in node.children)
    if node.kind == "choice":
        return "{ " + " | ".join(_render(item) for item in node.children) + " }"
    if node.kind == "optional":
        return "[" + _render(node.children[0]) + "]"
    if node.kind == "repeat":
        suffix = "?" if node.minimum == 0 and node.maximum == 1 else "+" if node.minimum == 1 else "*"
        return _render(node.children[0]) + suffix
    if node.kind == "choice_repeat":
        if node.minimum == 0:
            return "[ " + " | ".join(_render(item) for item in node.children) + " ]*"
        return "{ " + " | ".join(_render(item) for item in node.children) + " }*"
    raise InvariantError(f"Unsupported command expression node: {node.kind}")


def _render_literal(value: str, *, quoted: bool = False) -> str:
    canonical = value.casefold()
    needs_quote = not canonical or any(char.isspace() or char in _PUNCTUATION for char in canonical)
    if quoted and needs_quote:
        return json.dumps(canonical, ensure_ascii=False)
    if value == "|":
        return value if not quoted else json.dumps(canonical, ensure_ascii=False)
    if not needs_quote:
        return canonical
    return json.dumps(canonical, ensure_ascii=False)


def _entry_value(entry: Any, key: str) -> Any:
    if isinstance(entry, Mapping):
        return entry.get(key)
    return getattr(entry, key, None)


def _entry_mapping(entry: Any) -> dict[str, Any]:
    if isinstance(entry, Mapping):
        return dict(entry)
    values = {}
    for key in ("id", "key", "name", "description", "expression", "normalized_expression", "source", "version", "enabled"):
        value = getattr(entry, key, None)
        if value is not None:
            values[key] = value
    return values


__all__ = [
    "CommandExpression",
    "CommandMatch",
    "ExpressionNode",
    "MAX_COMMAND_TOKENS",
    "capture_catalog",
    "match_command_expression",
    "match_cli_expression",
    "next_command_tokens",
    "normalize_command_expression",
    "normalize_cli_expression",
    "parse_command_expression",
    "parse_cli_expression",
    "search_command_expressions",
]
