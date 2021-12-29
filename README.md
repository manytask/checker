# Manytask Checker

Students' solution checker

* git changes detection
* extension for different languages 
* sandbox execution
* [manytask](https://github.com/yandexdataschool/manytask) integration


TBA

---


## Structure 

### Course

* **CourseConfig**  
  Manage course configuration.  Wrapper around `.course.yml` file. 


* **CourseSchedule**  
  Manage course deadlines.  Wrapper around `.deadlines.yml` file. 


* **CourseDriver**  
  Manage mapping of the Course to the Filesystem. (e.g. map Task to folders with tests and source files)  
  Available layouts are:
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



## Adding a new course 

TBA
