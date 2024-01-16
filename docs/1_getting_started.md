# Getting Started

This page will help you to get started to use `checker` with your course.  

This guide assumes that you have already learned the [concepts](./0_concepts.md).


## Starting point

What you already have:

1. You are a going to create a course with manytask and checker.
2. You have installed (or going to install) [manytask](https://github.com/manytask/manytask).  
   (So you have empty public repo, private group for students and manytask instance running)

What you need to do:

1. Create a private repo with specific structure - [Layout](#layout)
2. Create a testing environment - [Testing environment](#testing-environment)
3. Configure your course - [Configuration](#configuration)
4. Learn how to test locally - [Local testing](#local-testing)
5. Learn how to setup Infrastructure - [Infrastructure](#infrastructure)
6. Learn how to set up CI in private and public repos - [CI setup](#ci-set-up)

A good starting point is to check out the [course-template](https://github.com/manytask/course-template). This is an example private repo for a python course with tests and tasks. You can fork it and use as a base for your course. 


## Layout

The private repository layout is crucial for the checker to function correctly. 
Each task should be organized into dedicated folders within group directories. 
Also, there are 2 config files `.course.yml` and `.deadlines.yml` that are required for checker to work.
Here's a detailed breakdown:

```yaml
group_1/
    task_1/
      .template/  # optional, can extract from solution files
        [some files]
      [gold solution files]
      [some private tests]
      [some public tests]
      .task.yml  # task config with default parameters overwriting
    task_2/
        ...
group_2/
    task_3/
        ...
    task_4/
        ...
.checker.yml  # checker config with default parameters and pipelines
.deadlines.yml  # deadlines config with task scores to send to manytask
```

!!! warning  
    Group and files naming have to be unique.

!!! note  
    By default ".*" files are considered as private and not copied to public repo, but you can change it in config.

Additionally, you can have any files in like `group_1/.lecture` folder or `tools/my_course_tools` folder.  
Also, probably you want to have `.docker` file with your test environment and `.gitlab-ci-students.yml` file to run tests in CI.

After [Configuration](#configuration), you can validate your layout with `checker validate` command.


## Testing environment

To run tests you need to have a docker testing environment that includes your course's specific environment and the pre-installed checker. Here’s how you can prepare and utilize it: 

You have 2 options:

1. Build you docker image from scratch and install checker there. This way you have full control and can minimize the size of the image as much as you like.
    The `checker` is available on pypi, so you can install it with pip
    ```shell
    pip install manytask-checker
    ```

2. Use checker pre-built base-docker image to base on. This way you can save some time and effort and just add your course-specific environment to the image.

    [//]: # (TODO: add pre-build docker image ref )
    ```shell
    FROM TBA:1.2.3
    ```


## Configuration

The configuration of the checker and Manytask requires setting up 2 main files: `.course.yml` and `.deadlines.yml` and custom `.task.yml` files for each task when needed. 
Here is the short overview of the configuration files:

* **Checker Configuration** (`.checker.yml`):  
  This file specifies the default parameters for the checker script and defines the pipelines for task checking and exporting.


* **Deadlines Configuration** (`.deadlines.yml`):
  This file outlines the deadlines for each group, task max score and etc.  
  In the checker it is used a) to validate deadlines integrity and b) to send scores to manytask.


* **Task Configuration** (`.task.yml`):
  Optional file located in task directory, this file allows for task-specific settings. It can override default parameters, private/public files and pipelines set in .checker.yml for individual tasks.


For the full guide on configuration, see the [Configuration docs](./2_configuration.md) page.


## Local testing

For local testing of private repo you have 2 options:

1. Install checker on your machine
    ```shell
    # create virtualenv
    python -m venv .venv
    source .venv/bin/activate
    # install checker
    (.venv) pip install manytask-checker
    ```
    And use it as a cli application from inside your private repo
    ```shell
    (.venv) checker check --task hello-world
    (.venv) checker check --group lecture-1
    (.venv) checker check
    ```


2. Use test environment docker you made before in interactive mode
   
    [//]: # (TODO: add pre-build docker image ref )
    ```shell
    # run docker in interactive mode mounting your repo as /course
    docker run -it --rm -v $(pwd):/course -w /course manytask/checker:latest bash
    ```
    And use it as a cli application from inside your private repo
    ```shell
    # inside docker
    > checker check --task hello-world
    > checker check --group lecture-1
    > checker check
    ```

!!! note 
    \#1 is faster and easier to debug, it is ok for local testing, \#2 ensure that your tests will run in the same environment as in CI.


## Infrastructure

Setting up the infrastructure for Manytask and checker involves configuring the runtime environment:

Manytask requite the following:

1. (optional) **Self-hosted GitLab** instance - storing public repo and students' repos.   
    Manytask and checker can work with gitlab.com, but you can use self-hosted gitlab instance for better control, privacy and performance.  
    Please refer to [gitlab docs](https://about.gitlab.com/install/) for installation instructions.


2. **Manytask instance** - web application managing students' grades (in google sheet) and deadlines (web page).  
    Please refer to [manytask docs](https://github.com/manytask/manytask).

So the checker extends it with the following:

1. **Gitlab Runner** - place where students' solutions will be tested.  
    You definitely need it as the students will consume your free CI minutes extremely fast.    
    Please refer to [gitlab runners docs](https://docs.gitlab.com/runner/) for installation instructions.  
    Add this runner as a student group runner to your course group or as a shared runner to your gitlab instance.


2. (optional) **GitHub Runner** - if you are using GitHub for your private repo, you may need to set up GitHub runner.  
    Please refer to [github runners docs](https://docs.github.com/en/actions/hosting-your-own-runners/about-self-hosted-runners) for installation instructions.  
    However, at the moment, GitHub provides 2000 CI minutes for org, so it may be to start with.


3. (optional) **Private Docker Registry** - to store testing environment docker image (it contains private tests).    
    You can use anything you like, but we recommend to use gitlab registry as it is already integrated with gitlab.


4. **Gitlab token** - with public repos access to export files to the public repo.  
    You need to add it as a secret to your private repo and use it in CI. Also if you want to use in it pipelines in students' repos, you need to add it as a secret to your course group.  
    If you have self-hosted gitlab instance or premium account, you can create service account for the course group using this [guide](https://docs.gitlab.com/ce/user/profile/service_accounts.html).  
    Otherwise, you have to create a separate account, grant access to the course group and use its [personal access token](https://docs.gitlab.com/ce/user/profile/personal_access_tokens.html). 

!!! note  
    For an automated setup, refer to the [manytask/infrastructure](https://github.com/manytask/infrastructure) repository with ansible playbooks.    
    These playbooks provide a stable and tested setup for the self-hosted gitlab instance, manytask instance and gitlab runners (configuration included).


## CI set up

Configuring Continuous Integration (CI) is essential for automating the testing and deployment processes. Here's how to set it up for both private and public repositories.  

1. **Private Repo**  
    You can refer to the [course-template](https://github.com/manytask/course-template) for an example of a private repo with CI set up.
    * Private repo on GitHub (recommended way)  
      If your private repo is on GitHub, you can use GitHub Actions and [Reusable Workflows](https://github.com/manytask/workflows) provided by us to set up CI in a few clicks.

    * Private repo on GitLab  
      If your private repo is on GitLab, you can use GitLab CI, no pre-configured workflows are available at the moment.
   
    You need to set up the following CI jobs:

    1. on each push/mr/release - build testing environment docker image and keep as artifact to run tests in.  
    2. on each push/mr - run `checker check` inside docker image to test gold solution against private and public tests.   
    3. on each push/release - run `checker export` inside docker image to export to the public repository (requires gitlab token).  
    4. on each push/release - call manytask api to update deadlines (requires manytask push token).  
    5. on each push/release - build and publish testing environment docker image to the private docker registry (requires gitlab token).
   
    !!! note
        Don't forget to add MANYTASK_TOKEN and GITLAB_TOKEN as protected secrets to your private repo. 


2. **Public Repo**  
    Checker will push to this repo automatically and no pipelines to run, so nothing to configure directly here.  
    However the public repo should have `.gitlab-ci-students.yml` file in the root to set up it as `external ci file` for all students' repositories.
    This file should contain 2 jobs, both running inside test environment docker image:

    1. on each push/mr - run `checker grade` to test solution against private and public tests and push scores to manytask (requires manytask push token).
    2. on each mr in public repo - run `checker check --contribute` to test contributed public tests against gold solution. 


3. **Students' Group**
    Students' repos will use groups or shared runners from this group, so make sure that they are enabled.

    !!! note  
        Don't forget to add MANYTASK_TOKEN and GITLAB_TOKEN (optional) as protected secrets to your group. 
