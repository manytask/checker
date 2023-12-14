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
