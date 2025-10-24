FROM rust:1.85.0-bookworm AS builder

WORKDIR /usr/src/app
COPY . .

RUN cargo build --release --manifest-path simeis-server/Cargo.toml

FROM debian:bookworm-slim

WORKDIR /app
COPY --from=builder /usr/src/app/target/release/simeis-server ./simeis-server

EXPOSE 8080
CMD ["./simeis-server"]