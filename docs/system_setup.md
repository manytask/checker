# Production setup

NB: First you need [manytask](https://github.com/yandexdataschool/manytask) up and running as checker is integrated with manytask only. 


Note: The following instructions assume you will use `checker`. If you are going to use custom `checker` with manytask - just read these docs for advices and approaches  


---

## Pre-setup

One-time actions necessary for the functioning of the entire repo

TBA


## Pre-requirements 

Also, please refet to the [manytask setup docs -> new-course/new-semester](https://github.com/yandexdataschool/manytask/blob/main/docs/system_setup.md#new-course) to get and set  up:

* (Self-hosted) gitlab to work with
  * public repo with assignments for students 
  * private group for students' repo 
* Virtual Machine/Server
* Running manytask instance


## Gitlab layout

This script will rely on the following layouts of the course repositories 

#### Private-repo (recommended)

The following layout allows you to push assignments automatically and fielder files students will see (for example hide all docker files or configs)

* `private-repo` - private repository with tasks, tests, ect
* `public-repo` - public repository with auto-exported tasks from `private-repo`
* private students' group 

So each student can see only `public-repo` repo and his/her own repo and can not access `private-repo`


#### Submodule (not recommended, but possible)

In this case auto-exporting of the tasks will not work. However, the task checking is still working.  

* `tasks` - public repository with assignments for students   
* `tests` - git submodule in `tasks`; private repository with tests and all private info 
* private students' group 

So each student can see only `tasks` repo and his/her own repo and can not access `tests`


## Gitlab runners 

To test students solutions you need gitlab-runner. We recommend yo to use [gitalb-runner in docker](https://docs.gitlab.com/runner/install/docker.html)

It's convenient to have 3 runners:
* `build` - runner for docker building
* `private-tester` - to check reference-solution and test... tests
* `public-tester` - to check and grade students' solutions 

See [examples/config.gitlab.toml](../examples/config.gitlab.toml)

All runners are created in course groups, so you can create them once.
- `build` and `private-tester` are attached to the admin/course folder (e.g `py-tasks`)
- `public-tester` is attached to the general students group (e.g `python`)


1. First you need to run gitlab runner itself, using [gitalb-runner in docker instruction](https://docs.gitlab.com/runner/install/docker.html) 
 
 
2. Register runners, following [register gitlab-runner with docker instruction](https://docs.gitlab.com/runner/register/index.html#docker)
   * Go to admin group -> CI/CD settings and register `build` and `private-tester`
   * Go to general students group -> CI/CD settings and register `public-tester`
   * It will register them in gitlab and generate `config.toml` in `/srv/gitlab-runner/config` 
   * Copy generated tokens from `config.toml` (you need to keep only tokens) and update `config.toml` to match [examples/config.gitlab.toml](../examples/config.gitlab.toml)  
   * reload gitlab runner to update config `docker restart gitlab-runner`

3. Check admin group and general students group to have active runners (3 in total) 


Note: Important detail - in public tester in [examples/config.gitlab.toml](../examples/config.gitlab.toml) you can see comparison of gitlab-ci config with original scored in docker. 
It's done for students not to change `.gitlab-ci.yml` file and set 100% score, for example


## docker

Gitlab runner operates and run dockers. So you need to create docker where test will be executed 

It's convenient to have 2 dockers: 

* `base` - 'empty' docker with libs and apps you will use for testing (as well as `checker` pkg)
* `testenv` - based on `base` docker with copied tests 

see [examples/base.docker](../examples/base.docker) and  [examples/testenv.docker](../examples/testenv.docker)

#### Docker registry 

Currently, the main registry is docker yandex cloud registry (credentials: @slon)  
Be ready to set `DOCKER_AUTH_CONFIG` and `DOCKER_PASS_JSON_KEY` to gitlab-runners config (see [examples/config.gitlab.toml](../examples/config.gitlab.toml))


## gitlab-ci

You need to create gitlab-ci config files for gitlab to run `checker` script commands. 

We offer to create 2 separate files:
* `.gitlab-ci.yml` - file with jobs to run in students repositories:  
    * `grade` job to general solutions testing 
    * `grade-mrs` job to test students' email
    * `check` job to check students contributions in the repo (run updated tests against authors' solutions)
* `.releaser-ci.yml` - file with jobs to run in private repo - test tasks, test tests, test course tools etc.
    * `build` job to build base docker 
    * `check-tools` some jobs to check course tools if any
    * `check-tasks` job with task testing 
    * `deploy` jobs to deploy testenv docker, manytask deadlines, public repo 
    * `manual` some jobs to run manually by tutors  

see [examples/.gitlab-ci.yml](../examples/.gitlab-ci.yml) and  [examples/.releaser-ci.yml](../examples/.releaser-ci.yml)

So you need to select in private repo CI/CD Settings `.releaser-ci.yml` as ci file.
