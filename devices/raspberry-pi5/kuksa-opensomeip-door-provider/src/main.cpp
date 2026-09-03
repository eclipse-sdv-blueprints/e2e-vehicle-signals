// /********************************************************************************
// * Copyright (c) 2026 Contributors to the Eclipse Foundation
// *
// * See the NOTICE file(s) distributed with this work for additional
// * information regarding copyright ownership.
// *
// * This program and the accompanying materials are made available under the
// * terms of the Apache License 2.0 which is available at
// * https://www.apache.org/licenses/LICENSE-2.0
// *
// * SPDX-License-Identifier: Apache-2.0
// ********************************************************************************/

#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include <someip/message.h>
#include <someip/types.h>
#include <transport/endpoint.h>
#include <transport/transport.h>
#include <transport/udp_transport.h>

#include "actuator_subscriber.h"
#include "collector_client.h"

namespace {

constexpr uint16_t kDoorServiceId = 0x4301;
constexpr uint16_t kDoorStateEventId = 0x8001;
constexpr uint16_t kDoorTargetEventId = 0x8002;
constexpr uint16_t kProviderClientId = 0xD001;
constexpr uint8_t kInterfaceVersion = 1;
constexpr char kDoorVssPath[] = "Vehicle.Cabin.Door.Row1.DriverSide.IsOpen";

std::atomic<bool> g_running{true};

void signal_handler(int) {
    g_running.store(false);
}

struct Options {
    std::string broker{"localhost:55555"};
    std::string bind_host{"0.0.0.0"};
    uint16_t bind_port{30500};
    std::string door_host{"192.168.88.101"};
    uint16_t door_port{30501};
};

uint16_t parse_port(const char* value, const char* option) {
    const unsigned long port = std::strtoul(value, nullptr, 10);
    if (port == 0 || port > 65535) {
        throw std::runtime_error(std::string("Invalid ") + option + " port: " + value);
    }
    return static_cast<uint16_t>(port);
}

Options parse_options(int argc, char* argv[]) {
    Options options;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--broker" && index + 1 < argc) {
            options.broker = argv[++index];
        } else if (argument == "--bind-host" && index + 1 < argc) {
            options.bind_host = argv[++index];
        } else if (argument == "--bind-port" && index + 1 < argc) {
            options.bind_port = parse_port(argv[++index], "bind");
        } else if (argument == "--door-host" && index + 1 < argc) {
            options.door_host = argv[++index];
        } else if (argument == "--door-port" && index + 1 < argc) {
            options.door_port = parse_port(argv[++index], "door");
        } else {
            throw std::runtime_error(
                "Usage: kuksa-opensomeip-door-provider "
                "[--broker host:port] [--bind-host address] [--bind-port port] "
                "[--door-host address] [--door-port port]");
        }
    }
    return options;
}

class DoorSomeipAdapter final : public someip::transport::ITransportListener {
public:
    DoorSomeipAdapter(std::shared_ptr<someip::transport::UdpTransport> transport,
                      someip::transport::Endpoint door_endpoint,
                      std::shared_ptr<sdv::broker_feeder::CollectorClient> client)
        : transport_(std::move(transport)),
          door_endpoint_(std::move(door_endpoint)),
          client_(std::move(client)) {}

    void on_message_received(someip::MessagePtr message,
                             const someip::transport::Endpoint&) override {
        if (!message || message->get_message_type() != someip::MessageType::NOTIFICATION ||
            message->get_service_id() != kDoorServiceId ||
            message->get_method_id() != kDoorStateEventId ||
            message->get_interface_version() != kInterfaceVersion) {
            return;
        }

        const auto& payload = message->get_payload();
        if (payload.size() != 1) {
            std::cerr << "Ignoring door state event with invalid payload size" << std::endl;
            return;
        }

        const bool is_open = payload[0] != 0;
        kuksa::val::v1::SetRequest request;
        auto* update = request.add_updates();
        update->mutable_entry()->set_path(kDoorVssPath);
        update->mutable_entry()->mutable_value()->set_bool_(is_open);
        update->add_fields(kuksa::val::v1::FIELD_VALUE);
        auto context = client_->createClientContext();
        kuksa::val::v1::SetResponse response;
        const grpc::Status status = client_->Set(context.get(), request, &response);
        if (!status.ok() || response.error().code() != 0) {
            client_->handleGrpcError(status, "DoorSomeipAdapter::on_message_received");
            std::cerr << "Failed to write door state to Kuksa" << std::endl;
            return;
        }
        std::cout << "Door state received: " << (is_open ? "open" : "closed") << std::endl;
    }

    void on_connection_lost(const someip::transport::Endpoint&) override {}
    void on_connection_established(const someip::transport::Endpoint&) override {}

    void on_error(someip::Result error) override {
        std::cerr << "OpenSOME/IP transport error: " << static_cast<int>(error) << std::endl;
    }

    void send_target(bool is_open) {
        const uint16_t session_id = next_session_id_++;
        someip::Message message(
            someip::MessageId(kDoorServiceId, kDoorTargetEventId),
            someip::RequestId(kProviderClientId, session_id),
            someip::MessageType::NOTIFICATION,
            someip::ReturnCode::E_OK);
        message.set_interface_version(kInterfaceVersion);
        const uint8_t payload[] = {static_cast<uint8_t>(is_open ? 1 : 0)};
        message.set_payload(payload, sizeof(payload));

        if (transport_->send_message(message, door_endpoint_) != someip::Result::SUCCESS) {
            std::cerr << "Failed to send door target" << std::endl;
            return;
        }
        std::cout << "Door target sent: " << (is_open ? "open" : "closed") << std::endl;
    }

private:
    std::shared_ptr<someip::transport::UdpTransport> transport_;
    someip::transport::Endpoint door_endpoint_;
    std::shared_ptr<sdv::broker_feeder::CollectorClient> client_;
    uint16_t next_session_id_{1};
};

bool target_value_as_bool(const kuksa::val::v1::Datapoint& value, bool* result) {
    if (value.value_case() != kuksa::val::v1::Datapoint::kBool) {
        return false;
    }
    *result = value.bool_();
    return true;
}

}  // namespace

int main(int argc, char* argv[]) {
    try {
        const Options options = parse_options(argc, argv);
        std::signal(SIGINT, signal_handler);
        std::signal(SIGTERM, signal_handler);

        auto client = sdv::broker_feeder::CollectorClient::createInstance(options.broker);
        auto target_subscriber = sdv::broker_feeder::kuksa::ActuatorSubscriber::createInstance(client);

        someip::transport::UdpTransportConfig transport_config;
        transport_config.blocking = true;
        transport_config.reuse_address = true;
        transport_config.max_message_size = 1400;
        auto transport = std::make_shared<someip::transport::UdpTransport>(
            someip::transport::Endpoint(options.bind_host, options.bind_port), transport_config);
        DoorSomeipAdapter adapter(
            transport,
            someip::transport::Endpoint(options.door_host, options.door_port),
            client);
        transport->set_listener(&adapter);

        target_subscriber->Init(
            {kDoorVssPath},
            [&adapter](const sdv::broker_feeder::kuksa::ActuatorValues& values) {
                const auto target = values.find(kDoorVssPath);
                bool is_open = false;
                if (target == values.end() || !target_value_as_bool(target->second, &is_open)) {
                    std::cerr << "Ignoring door target with a non-boolean value" << std::endl;
                    return;
                }
                adapter.send_target(is_open);
            });

        std::thread target_thread([&target_subscriber] { target_subscriber->Run(); });
        if (transport->start() != someip::Result::SUCCESS) {
            std::cerr << "Failed to start OpenSOME/IP UDP transport" << std::endl;
            g_running.store(false);
        }

        std::cout << "Kuksa OpenSOME/IP door provider listening on "
                  << options.bind_host << ':' << options.bind_port << std::endl;
        while (g_running.load()) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }

        transport->set_listener(nullptr);
        transport->stop();
        target_subscriber->Shutdown();
        target_thread.join();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << std::endl;
        return 1;
    }
}
