(module
  (import "lifehub" "call_interface_json"
    (func $call (param i32 i32 i32 i32 i32 i32) (result i32)))
  (memory (export "memory") 1)
  (data (i32.const 0) "example.heartbeat@1")
  (data (i32.const 64) "{}")
  (func (export "run") (result i32)
    (local $position i32) (local $counter i32)
    (if (i32.ne (call $call (i32.const 0) (i32.const 19)
      (i32.const 64) (i32.const 2) (i32.const 128) (i32.const 128)) (i32.const 18))
      (then unreachable))
    (local.set $position (i32.const 138))
    (loop $digit
      (local.set $counter (i32.add (i32.mul (local.get $counter) (i32.const 10))
        (i32.sub (i32.load8_u (local.get $position)) (i32.const 48))))
      (local.set $position (i32.add (local.get $position) (i32.const 1)))
      (br_if $digit (i32.lt_u (local.get $position) (i32.const 144))))
    local.get $counter))
