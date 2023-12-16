from __future__ import annotations

from typing import Optional

from pydantic import Field, model_validator

from .checker import (
    CheckerParametersConfig,
    CheckerStructureConfig,
    PipelineStageConfig,
)
from .utils import CustomBaseModel, YamlLoaderMixin


class TaskConfig(CustomBaseModel, YamlLoaderMixin['TaskConfig']):
    """Task configuration file."""

    version: int  # if config exists, version is always present

    # Note: use Optional[...] instead of ... | None as pydantic does not support | in older python versions
    structure: Optional[CheckerStructureConfig] = None
    parameters: Optional[CheckerParametersConfig] = None
    task_pipeline: Optional[list[PipelineStageConfig]] = None
    report_pipeline: Optional[list[PipelineStageConfig]] = None
