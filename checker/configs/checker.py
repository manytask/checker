from __future__ import annotations

from enum import Enum
from typing import Any, Union

from pydantic import AnyUrl, Field, RootModel, ValidationError, field_validator

from .utils import CustomBaseModel, YamlLoaderMixin


# Note: old Union style in definition for backward compatibility
ParamType = Union[bool, int, float, str, list[Union[int, float, str, None]], None]
TTemplate = Union[str, list[Union[ParamType, str]], dict[str, Union[ParamType, str]]]


class CheckerStructureConfig(CustomBaseModel):
    ignore_patterns: list[str] | None = None
    private_patterns: list[str] | None = None
    public_patterns: list[str] | None = None
    # TODO: add check "**" is not allowed


class CheckerParametersConfig(RootModel[dict[str, ParamType]]):
    root: dict[str, ParamType]

    def __getitem__(self, item: str) -> ParamType:
        return self.root[item]

    @property
    def __dict__(self) -> dict[str, ParamType]:
        return self.root


class CheckerExportConfig(CustomBaseModel):
    class TemplateType(Enum):
        SEARCH = "search"
        CREATE = "create"

    destination: AnyUrl
    default_branch: str = "main"
    commit_message: str = "chore(auto): export new tasks"
    templates: TemplateType = TemplateType.SEARCH


class PipelineStageConfig(CustomBaseModel):
    class FailType(Enum):
        FAST = "fast"
        AFTER_ALL = "after_all"
        NEVER = "never"

    name: str
    run: str

    args: dict[str, ParamType | TTemplate] = Field(default_factory=dict)

    run_if: bool | TTemplate | None = None
    fail: FailType = FailType.FAST

    # save pipline stage result to context under this key
    register_output: str | None = None


class CheckerTestingConfig(CustomBaseModel):
    class ChangesDetectionType(Enum):
        BRANCH_NAME = "branch_name"
        COMMIT_MESSAGE = "commit_message"
        LAST_COMMIT_CHANGES = "last_commit_changes"
        FILES_CHANGED = "files_changed"

    changes_detection: ChangesDetectionType = ChangesDetectionType.LAST_COMMIT_CHANGES

    search_plugins: list[str] = Field(default_factory=list)

    global_pipeline: list[PipelineStageConfig] = Field(default_factory=list)
    tasks_pipeline: list[PipelineStageConfig] = Field(default_factory=list)
    report_pipeline: list[PipelineStageConfig] = Field(default_factory=list)


class CheckerConfig(CustomBaseModel, YamlLoaderMixin['CheckerConfig']):
    """
    Checker configuration.
    :ivar version: config version
    :ivar default_parameters: default parameters for task pipeline
    :ivar structure: describe the structure of the repo - private/public and allowed for change files
    :ivar export: describe export (publishing to public repo)
    :ivar manytask: describe connection to manytask
    :ivar testing: describe testing/checking - pipeline, isolation etc
    """

    version: int

    default_parameters: CheckerParametersConfig = Field(default_factory=dict)

    structure: CheckerStructureConfig
    export: CheckerExportConfig
    testing: CheckerTestingConfig

    @field_validator("version")
    @classmethod
    def check_version(cls, v: int) -> None:
        if v != 1:
            raise ValidationError(f"Only version 1 is supported for {cls.__name__}")
