from __future__ import annotations

from pydantic import Field, model_validator

from .checker import (
    CheckerParametersConfig,
    CheckerStructureConfig,
    PipelineStageConfig,
)
from .utils import CustomBaseModel, YamlLoaderMixin


class TaskConfig(CustomBaseModel, YamlLoaderMixin):
    """Task configuration file."""

    version: int  # if config exists, version is always present

    structure: CheckerStructureConfig | None = None
    parameters: CheckerParametersConfig | None = None
    task_pipeline: list[PipelineStageConfig] | None = None
    report_pipeline: list[PipelineStageConfig] | None = None
