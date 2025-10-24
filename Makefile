build:
	RUSTFLAGS="-C code-model=kernel -C codegen-units=1" cargo build --release --package simeis-server

	strip target/release/simeis-server

test:
	cargo test

testf:
	cargo run > /dev/null 2>&1 &
	sleep 10
	python -m example.test.testClient
	
manual:
	typst compile doc/manual.typ manual.pdf

check:
	cargo check
	cargo fmt --check
	cargo clippy

clean:
	cargo clean

update:
	cargo update