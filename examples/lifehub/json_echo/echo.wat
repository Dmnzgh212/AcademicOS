(module
  (import "lifehub_service" "read_request"
    (func $read (param i32 i32) (result i32)))
  (import "lifehub_service" "write_response"
    (func $write (param i32 i32) (result i32)))
  (memory (export "memory") 1)
  (func (export "run") (result i32) (local $n i32)
    (local.set $n (call $read (i32.const 0) (i32.const 65536)))
    (if (i32.lt_s (local.get $n) (i32.const 0)) (then unreachable))
    (drop (call $write (i32.const 0) (local.get $n)))
    (i32.const 0)))
