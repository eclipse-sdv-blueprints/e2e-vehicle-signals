# /********************************************************************************
# * Copyright (c) 2026 Contributors to the Eclipse Foundation
# *
# * See the NOTICE file(s) distributed with this work for additional
# * information regarding copyright ownership.
# *
# * This program and the accompanying materials are made available under the
# * terms of the Apache License 2.0 which is available at
# * https://www.apache.org/licenses/LICENSE-2.0
# *
# * SPDX-License-Identifier: Apache-2.0
# ********************************************************************************/

cmake_minimum_required(VERSION 3.20)
project(kuksa_opensomeip_door_provider LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(BUILD_TESTS OFF CACHE BOOL "Disable OpenSOME/IP tests in the provider image" FORCE)
set(BUILD_EXAMPLES OFF CACHE BOOL "Disable OpenSOME/IP examples in the provider image" FORCE)
set(OPENSOMEIP_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../external/opensomeip"
    CACHE PATH "Path to the vtz/opensomeip source tree")

add_subdirectory(${OPENSOMEIP_SOURCE_DIR}
                 ${CMAKE_CURRENT_BINARY_DIR}/opensomeip)
add_subdirectory(third_party/broker_feeder)

add_executable(kuksa-opensomeip-door-provider src/main.cpp)
target_link_libraries(kuksa-opensomeip-door-provider PRIVATE opensomeip data_broker_feeder)
target_include_directories(kuksa-opensomeip-door-provider PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/broker_feeder)
