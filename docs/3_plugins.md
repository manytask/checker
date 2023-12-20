# Plugins

This page describes how to use and write plugins for checker pipelines.

You can refer to the [course-template](https://github.com/manytask/course-template) repository for examples of plugins usage and custom plugins development.


## What is the Plugin

Plugin is a single stage of the pipeline, have arguments, return exclusion result. 
In a nutshell, it is a Python class overriding abstract class `checker.plugins.PluginABC`:

> ::: checker.plugins.base.PluginABC

Note that each plugin should override `checker.plugins.PluginABC.Args` class to provide arguments validation. Otherwise, empty arguments will be passed to `run` method.

> ::: checker.plugins.base.PluginABC.Args


Each plugin output `checker.plugins.PluginOutput` class when executed successfully. 

> ::: checker.plugins.base.PluginOutput

In case of error, `checker.exceptions.PluginExecutionFailed` have to be raised.
> ::: checker.exceptions.PluginExecutionFailed

!!! note  
    Base Plugin class will handle all ValidationErrors of Args and raise error by itself.  
    So try to move all arguments validation to `Args` class in `pydantic` way.


## How to use plugins

Plugins are used in the pipelines described in `.checker.yml` file. When running a pipeline the checker will validate plugin arguments and run it.

The following plugins are available out of the box:

TBA

[//]: # (::: checker.plugins)

[//]: # (    handler: python)

[//]: # (TODO: list here all plugins available out of the box)


## How to write a custom plugin

To write a custom plugin you need to create a class inheriting from `checker.plugins.PluginABC` and override `_run` method, `Args` inner class and set `name` class attribute.

[//]: # (TODO: test example)

```python
from random import randint
from checker.plugins import PluginABC, PluginOutput
from checker.exceptions import PluginExecutionFailed
from pydantic import AnyUrl

class PrintUrlPlugin(PluginABC):
    """Plugin to print url"""

    name = "print_url"

    class Args(PluginABC.Args):
        url: AnyUrl

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:
        if randint(0, 1):
            if verbose:
                raise PluginExecutionFailed("Verbose error, we got randint=1")
            else:
                raise PluginExecutionFailed("Random error")
        
        return PluginOutput(
            output=f"Url is {args.url}",
            percentage=1.0,  # optional, default 1.0 on success
        )
```

!!! important  
    The Plugin must implement `verbose` functionality!  
    If `verbose` is `True` the plugin should provide all info and possible debug info.  
    If `verbose` is `False` the plugin should provide only public-friendly info, e.g. excluding private test output.

!!! note
    It is a nice practice to write a small tests for your custom plugins to be sure that it works as expected.
