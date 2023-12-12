project(test_cpp_course)

cmake_minimum_required(VERSION 3.5)

set(CMAKE_CXX_STANDARD             17)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}")
set(CMAKE_EXPORT_COMPILE_COMMANDS  ON)

add_executable(test_foo foo/test.cpp)
