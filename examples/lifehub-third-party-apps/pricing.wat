;; Independently authored headless provider: unit price is three cents.
;; Input:  {"units":7}
;; Output: {"total":21}
;; This intentionally tiny JSON ABI is a compatibility proof, not the final SDK.
(module
  (import "lifehub_service" "read_request"
    (func $read (param i32 i32) (result i32)))
  (import "lifehub_service" "write_response"
    (func $write (param i32 i32) (result i32)))
  (memory (export "memory") 1)
  (data (i32.const 512) "{\"total\":00}")

  (func (export "run") (result i32)
    (local $length i32)
    (local $units i32)
    (local $total i32)

    (local.set $length (call $read (i32.const 0) (i32.const 128)))
    (if (i32.ne (local.get $length) (i32.const 11))
      (then unreachable))
    (if (i32.ne (i32.load8_u (i32.const 0)) (i32.const 123))
      (then unreachable))
    (local.set $units
      (i32.sub (i32.load8_u (i32.const 9)) (i32.const 48)))
    (if (i32.gt_u (local.get $units) (i32.const 9))
      (then unreachable))

    (local.set $total (i32.mul (local.get $units) (i32.const 3)))
    (i32.store8 (i32.const 521)
      (i32.add (i32.const 48)
        (i32.div_u (local.get $total) (i32.const 10))))
    (i32.store8 (i32.const 522)
      (i32.add (i32.const 48)
        (i32.rem_u (local.get $total) (i32.const 10))))
    (drop (call $write (i32.const 512) (i32.const 12)))
    (i32.const 0))
)
