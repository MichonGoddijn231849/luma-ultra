cmake_minimum_required(VERSION 3.21)
project(inair_viture_bridge LANGUAGES CXX)

add_library(inair_dll SHARED inair_dll.cpp)

target_compile_features(inair_dll PRIVATE cxx_std_17)

if(MSVC)
  set_property(TARGET inair_dll PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded")
endif()

set_target_properties(
  inair_dll
  PROPERTIES
    OUTPUT_NAME "inair_dll"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/out"
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}/out"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/out"
    ARCHIVE_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}/out"
)
