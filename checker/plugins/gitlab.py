from pydantic import AnyUrl

from .base import PluginABC


class CheckGitlabMergeRequestPlugin(PluginABC):
    """Plugin for checking gitlab merge request."""

    name = "check_gitlab_merge_request"

    class Args(PluginABC.Args):
        token: str
        task_dir: str
        repo_url: AnyUrl
        requre_approval: bool = False
        search_for_score: bool = False

    def _run(self, args: Args, *, verbose: bool = False) -> str:
        # TODO: implement
        print("TODO: implement")
