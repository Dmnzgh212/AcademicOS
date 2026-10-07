;; Independently authored headless consumer.
;; Calls example.pricing@1 through Engine routing, never selects a provider.
;; Returns the calculated total (21), not merely a response byte count.
(module
  (import "lifehub" "call_interface_json"
    (func $call (param i32 i32 i32 i32 i32 i32) (result i32)))
  (memory (export "memory") 1)
  (data (i32.const 0) "example.pricing@1")
  (data (i32.const 64) "{\"units\":7}")

  (func (export "run") (result i32)
    (local $length i32)
    (local.set $length
      (call $call
        (i32.const 0) (i32.const 17)
        (i32.const 64) (i32.const 11)
        (i32.const 128) (i32.const 128)))
    (if (i32.ne (local.get $length) (i32.const 12))
      (then unreachable))
    (if (i32.ne (i32.load8_u (i32.const 128)) (i32.const 123))
      (then unreachable))
    (if (i32.ne (i32.load8_u (i32.const 139)) (i32.const 125))
      (then unreachable))
    (i32.add
      (i32.mul
        (i32.sub (i32.load8_u (i32.const 137)) (i32.const 48))
        (i32.const 10))
      (i32.sub (i32.load8_u (i32.const 138)) (i32.const 48))))
)
