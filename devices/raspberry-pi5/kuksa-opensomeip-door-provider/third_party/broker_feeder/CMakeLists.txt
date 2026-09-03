#********************************************************************************
# Copyright (c) 2022 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License 2.0 which is available at
# http://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
#*******************************************************************************/

# Data Broker Proto file
set(PROTO_SOURCE_DIR ${PROJECT_SOURCE_DIR}/third_party/kuksa_data_broker)

find_package(Protobuf REQUIRED)
find_package(gRPC REQUIRED)

# Needed for cross build, env vars set via conan env_generator
find_program(PROTOC_PROGRAM_TEMP NAMES protoc REQUIRED)
set_property(TARGET protobuf::protoc PROPERTY IMPORTED_LOCATION "${PROTOC_PROGRAM_TEMP}")

# Needed for cross build, env vars set via conan env_generator
#   Do not use previously found program (GRPC_CPP_PLUGIN_PROGRAM) but new varaible: GRPC_CPP_PLUGIN_PROGRAM_ENV
find_program(GRPC_CPP_PLUGIN_PROGRAM_ENV NAMES grpc_cpp_plugin REQUIRED)

message("--- [broker_feedder] Using protoc: ${PROTOC_PROGRAM_TEMP}")
message("--- [broker_feedder] Using grpc_cpp_plugin: ${GRPC_CPP_PLUGIN_PROGRAM_ENV}")
message("--- [broker_feedder] protoc version:")
execute_process (
  COMMAND "${PROTOC_PROGRAM_TEMP}" --version
)

add_library(data_broker_feeder
  STATIC
    data_broker_feeder.cc
    collector_client.cc
    actuator_subscriber.cc
)

target_link_libraries(data_broker_feeder
  PUBLIC
    protobuf::libprotobuf
    gRPC::grpc++
    gRPC::grpc++_reflection
)

target_include_directories(data_broker_feeder
  PUBLIC
    ${CMAKE_CURRENT_BINARY_DIR}/generated
    ${CMAKE_CURRENT_SOURCE_DIR}
)

set(PROTO_GENERATED_DIR ${CMAKE_CURRENT_BINARY_DIR}/generated)
file(MAKE_DIRECTORY ${PROTO_GENERATED_DIR})
set(PROTO_FILES
  sdv/databroker/v1/broker.proto
  sdv/databroker/v1/collector.proto
  sdv/databroker/v1/types.proto
  kuksa/val/v1/types.proto
  kuksa/val/v1/val.proto
)
set(GRPC_SERVICE_PROTO_FILES
  sdv/databroker/v1/broker.proto
  sdv/databroker/v1/collector.proto
  kuksa/val/v1/val.proto
)
set(PROTO_GENERATED_OUTPUTS)

# Generate into a known directory. The upstream protobuf_generate() invocation
# derives paths from the feeder directory even though the protos are vendored
# beside it, so CMake tries to compile files protoc did not create.
foreach(PROTO_FILE IN LISTS PROTO_FILES)
  string(REPLACE ".proto" ".pb.cc" PROTO_CPP ${PROTO_FILE})
  string(REPLACE ".proto" ".pb.h" PROTO_HEADER ${PROTO_FILE})
  add_custom_command(
    OUTPUT ${PROTO_GENERATED_DIR}/${PROTO_CPP} ${PROTO_GENERATED_DIR}/${PROTO_HEADER}
    COMMAND ${PROTOC_PROGRAM_TEMP}
    ARGS --cpp_out=${PROTO_GENERATED_DIR} -I ${PROTO_SOURCE_DIR}
         ${PROTO_SOURCE_DIR}/${PROTO_FILE}
    DEPENDS ${PROTO_SOURCE_DIR}/${PROTO_FILE}
    VERBATIM)
  target_sources(data_broker_feeder PRIVATE ${PROTO_GENERATED_DIR}/${PROTO_CPP})
  list(APPEND PROTO_GENERATED_OUTPUTS
       ${PROTO_GENERATED_DIR}/${PROTO_CPP} ${PROTO_GENERATED_DIR}/${PROTO_HEADER})
endforeach()

foreach(PROTO_FILE IN LISTS GRPC_SERVICE_PROTO_FILES)
  string(REPLACE ".proto" ".grpc.pb.cc" GRPC_CPP ${PROTO_FILE})
  string(REPLACE ".proto" ".grpc.pb.h" GRPC_HEADER ${PROTO_FILE})
  add_custom_command(
    OUTPUT ${PROTO_GENERATED_DIR}/${GRPC_CPP} ${PROTO_GENERATED_DIR}/${GRPC_HEADER}
    COMMAND ${PROTOC_PROGRAM_TEMP}
    ARGS --grpc_out=${PROTO_GENERATED_DIR}
         --plugin=protoc-gen-grpc=${GRPC_CPP_PLUGIN_PROGRAM_ENV}
         -I ${PROTO_SOURCE_DIR} ${PROTO_SOURCE_DIR}/${PROTO_FILE}
    DEPENDS ${PROTO_SOURCE_DIR}/${PROTO_FILE}
    VERBATIM)
  target_sources(data_broker_feeder PRIVATE ${PROTO_GENERATED_DIR}/${GRPC_CPP})
  list(APPEND PROTO_GENERATED_OUTPUTS
       ${PROTO_GENERATED_DIR}/${GRPC_CPP} ${PROTO_GENERATED_DIR}/${GRPC_HEADER})
endforeach()

# Ensure generated imported headers exist before parallel object compilation.
add_custom_target(data_broker_proto_generated DEPENDS ${PROTO_GENERATED_OUTPUTS})
add_dependencies(data_broker_feeder data_broker_proto_generated)
