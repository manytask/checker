# Manytask Checker

[![Test](https://github.com/yandexdataschool/checker/actions/workflows/test.yml/badge.svg)](https://github.com/yandexdataschool/checker/actions/workflows/test.yml)
[![Publish](https://github.com/yandexdataschool/checker/actions/workflows/publish.yml/badge.svg)](https://github.com/yandexdataschool/checker/actions/workflows/publish.yml)
[![codecov](https://codecov.io/gh/yandexdataschool/checker/branch/main/graph/badge.svg?token=3F9J850FX2)](https://codecov.io/gh/yandexdataschool/checker)
[![github](https://img.shields.io/github/v/release/yandexdataschool/checker?logo=github&display_name=tag&sort=semver)](https://github.com/yandexdataschool/checker/releases)
[![docker](https://img.shields.io/pypi/v/manytask-checker.svg)](https://pypi.org/project/manytask-checker/)


Script to test students' solutions with [manytask](https://github.com/yandexdataschool/manytask) integration

Key features:

* git changes detection
* extension for different languages 
* sandbox execution
* [manytask](https://github.com/yandexdataschool/manytask) integration


Please refer to the [manytask](https://github.com/yandexdataschool/manytask) documentation first to understand the drill

---


## How it works 

The `checker` lib is a relatively small cli script aiming to run tests in gitlab runner and push results to `manytask`. 


The full `checker` and `manytask` setup roughly looks as follows

* self-hosted `gitlab` instance - storing repos with assignments and students' repo  
  * private repo - a repository with tasks, public and private tests, gold solutions, ect.
  * public repo - a repository available to students with tasks and solution templates
  * students' group - the group where `manytask` will create repositories for students  
    each students' repo - fork from public repo
* `gitlab runners` - place where students' solutions likely to be tested 
* `checker` script - some script to test students' solutions and push scores/grades to the `manytask`  
* `manytask` instance - web application managing students' grades (in google sheet) and deadlines (web page)  


The flow for checking students' solution looks like: 

1. Student push his solution to a gitlab repo
2. gitlab-ci runs separate docker in gitlab-runner
3. gitlab-ci runs this script with some parameters
4. the script detect the latest changes (via git) and select tasks to check
5. the tasks forwarded to `tester` and it returns obtained scores 
6. the script push student scores to the manytask 

(additionally script can check ground-truth solutions, export new tasks etc)


## Usage 

### Pre requirements  

1. [manytask](https://github.com/yandexdataschool/manytask) web app
   Currently, this lib is integrated with manytask **only**, 
   so you need it to be set up first, see installation instructions in manytask repo.
2. gitlab with access to greate groups, users and add runners  
   This pre-requirement for manytask; See manytask installation instructions for more info
3. Created and tested [tester](./checker/testers) for your course/language 

### Preparations 

Obtain service keys for this script to operate 
1. manytask tester token you set up when run it
2. gitlab service user to operate with your repositories  
   (better to create a new one)

Create gitlab repositories layout 

1. Create private repository with tasks, public and private tests and ground-truth solution;  
   Choose one of the suitable layouts (see [driver.py](./checker/course/driver.py))  
   Grant access to your service account 
2. Create public empty repository  
   Grant access to your service account  
3. Create private (!) group for students repositories  
   (You have already done it if you set up manytask)  
   Grant access to your service account 

Edit config files in repository 

1. `.course.yml` - main endpoints config  
   (see [.course.yml example](./examples/.course.yml))
2. `.deadlines.yml` - task deadlines 
   (see [.deadlines.yml example](./examples/.deadlines.yml))
3. `.gitlab-ci.yml` - set up gitlab ci pipeline to test students tasks 
4. `.releaser-ci.yml` - set up gitlab ci pipeline to test new added tasks and build dockers

Setup dockers with env ready for testing, it's convenient to have 2 dockers: 

1. `base.docker` - base docker to build and test students solutions, install lib here 
2. `testenv.docker` - docker on top of base docker, to save tasks and tests


## Structure 

### Course

* **CourseConfig**  
  Manage course configuration. Wrapper around `.course.yml` file. 


* **CourseSchedule**  
  Manage course deadlines. Wrapper around `.deadlines.yml` file. 


* **CourseDriver**  
  Manage mapping of the Course to the Filesystem. (e.g. map Task to folders with tests and source files)  
  Available layouts are (see [driver.py](./checker/course/driver.py)):
  * `flat` - all tasks in root folder of the repo
  * `groups` - each group has its own folder


### Testing 

* **Executor** is object to run commands with some isolation level.  
  Available modes are: 

  * `sandbox` - separate process (clean env variables, nouser/nogroup, disabled network)  
  * `docker` - TODO
  

* **Tester** is object which can test single task: copy files, build, test it, cleanup.  
  Tester is extendable for each course/language. Now available:

  * `python`


## Developing 

### Installation 

Create venv 
```shell
python -m venv .venv
source .venv/bin/activate
```

Install lib in dev mode
```shell
(.venv)$ pip install -U --editable .[test]  # .\[test\] in zsh 
```

### Running tests and linters 

```shell
pytest . --cpp --python
```

```shell
ruff checker
mypy checker
isort --check .
```

### Adding a new language tester

In order to add a new language to the test system you need to make a pull request.

1. Add a new tester in [checker/testers](./checker/testers)  
   (see [python.py](./checker/testers/python.py) as example)
2. Update [tester.py](./checker/testers/tester.py) `create` method to run your tester
3. Write tests for a new tester in [./tests/testers](./tests/testers)
