from __future__ import annotations

from pathlib import Path
from typing import Any, Generic, TypeVar

import pydantic
import yaml

from ..exceptions import BadConfig


class CustomBaseModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", validate_default=True)


T = TypeVar('T', bound=pydantic.BaseModel)


class YamlLoaderMixin(Generic[T]):
    @classmethod
    def from_yaml(cls: type[T], path: Path) -> T:
        try:
            with path.open() as f:
                return cls(**yaml.safe_load(f))
        except FileNotFoundError:
            raise BadConfig(f"File {path} not found")
        except TypeError as e:
            raise BadConfig(f"Config YAML error:\n{e}")
        except yaml.YAMLError as e:
            raise BadConfig(f"Config YAML error:\n{e}")
        except pydantic.ValidationError as e:
            raise BadConfig(f"Config Validation error:\n{e}")

    def to_yaml(self: T, path: Path) -> None:
        with path.open("w") as f:
            yaml.dump(self.model_dump(), f)

    @classmethod
    def get_json_schema(cls: type[T]) -> dict[str, Any]:
        return cls.model_json_schema()
