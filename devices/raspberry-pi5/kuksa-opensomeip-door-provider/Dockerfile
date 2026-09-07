FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    g++ \
    libgrpc++-dev \
    libprotobuf-dev \
    make \
    protobuf-compiler \
    protobuf-compiler-grpc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY external/opensomeip /opensomeip
COPY devices/raspberry-pi5/kuksa-opensomeip-door-provider /app
RUN rm -rf /app/build \
    && cmake -S . -B build -DBUILD_TESTS=OFF -DBUILD_EXAMPLES=OFF -DOPENSOMEIP_SOURCE_DIR=/opensomeip \
    && cmake --build build --parallel

ENTRYPOINT ["/app/build/kuksa-opensomeip-door-provider"]
