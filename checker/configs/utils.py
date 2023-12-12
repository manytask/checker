import re
from pathlib import Path
from typing import Any

import pydantic
import yaml

from ..exceptions import BadConfig


class CustomBaseModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", validate_default=True)


class YamlLoaderMixin:
    @classmethod
    def from_yaml(cls, path: Path) -> "YamlLoaderMixin":
        try:
            with path.open() as f:
                return cls(**yaml.safe_load(f))
        except FileNotFoundError:
            raise BadConfig(f"File {path} not found")
        except yaml.YAMLError as e:
            raise BadConfig(f"Config YAML error:\n{e}")
        except pydantic.ValidationError as e:
            raise BadConfig(f"Config Validation error:\n{e}")

    def to_yaml(self, path: Path) -> None:
        with path.open("w") as f:
            yaml.dump(self.dict(), f)


class ParametersResolver:
    """
    A simple resolver that can handle expressions in the config files like ${{ some expression here }}.
    The following syntax is supported:
    0. you can use bool, null/None, int, float, str and flat list types
    1. context consists of parameters from the config file and environment variables

    """

    pattern = re.compile(r"\${{\s*(!?\w+)\s*}}", re.DOTALL)  # "some ${{ var }} string"
    full_pattern = re.compile(r"^\${{\s*(!?\w+)\s*}}$", re.DOTALL)  # "${{ var }}"

    def __init__(self, context: dict[str, Any]):
        self.default_context = context
        self._validate_context(context)

    def _validate_context(self, context: dict[str, Any]) -> None:
        for value in context.values():
            if not isinstance(value, (bool, type(None), int, float, str, list)):
                raise BadConfig(f"Expression resolver does not support {type(value)} type of {value}")

    def _evaluate_single_expression(self, variable: Any, context: dict[str, Any]) -> Any:
        """Evaluate a single variable from the context."""
        # TODO: fix ! - not expression
        not_in_expression = '!' in variable
        variable = variable.replace("!", "")

        if variable in context:
            result = context[variable]
            if not_in_expression:
                # Note: cast to bool for not expression
                # raise BadConfig(f"Expression resolver does not support {type(result)} type of {result}")
                return not result
            else:
                return result
        else:
            raise BadConfig(f"Variable '{variable}' not found in context")

    def resolve(self, arguments: dict[str, Any], extra_context: dict[str, Any]) -> dict[str, Any]:
        """
        Resolve the arguments.
        :param arguments: arguments with expressions to resolve,
                          some string with placeholders e.g. "Some ${{ var }} string"
        :param extra_context: extra context to use for resolving
        :return: resolved expression string, resolved if only expression found or original expression if no placeholders

        Examples (individual expressions), where var = 1, var2 = 2 ints:
        "Some ${{ var }} string" -> "Some 1 string"
        "Some ${{ var }} string ${{ var2 }}" -> "Some 1 string 2"
        "${{ var }}" -> 1 (int type)
        "${{ var }} " -> "1 " (cast to str type)
        """
        return {key: self.resolve_single_param(value, extra_context) for key, value in arguments.items()}

    def resolve_single_param(self, expression: Any | list[Any], extra_context: dict[str, Any]) -> Any:
        if isinstance(expression, list):
            return [self.resolve_single_param(item, extra_context) for item in expression]
        else:
            if isinstance(expression, str):
                return self.resolve_single_string(expression, extra_context)
            else:
                return expression

    def resolve_single_string(self, expression: str, extra_context: dict[str, Any]) -> Any:
        self._validate_context(extra_context)
        context = self.default_context | extra_context

        # If the entire string is one placeholder, return its actual type
        full_match = self.full_pattern.fullmatch(expression)
        if full_match:
            return self._evaluate_single_expression(full_match.group(1), context)

        # If not, substitute and return the result as a string
        def substitute(match: re.Match) -> str:
            return str(self._evaluate_single_expression(match.group(1), context))

        resolved_expression = self.pattern.sub(substitute, expression)
        return resolved_expression
