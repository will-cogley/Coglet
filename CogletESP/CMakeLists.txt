# For more information about build system see
# https://docs.espressif.com/projects/esp-idf/en/latest/api-guides/build-system.html
# The following five lines of boilerplate have to be in your project's
# CMakeLists in this exact order for cmake to work correctly
cmake_minimum_required(VERSION 3.16)

# Coglet firmware version: plain numbers (the OTA check parses each part).
# Release builds set it from the tag: idf.py -D PROJECT_VER=2.3.0 build
if(NOT DEFINED PROJECT_VER)
    set(PROJECT_VER "2.4.2")
endif()

# Add this line to disable the specific warning
add_compile_options(-Wno-missing-field-initializers)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(xiaozhi)

