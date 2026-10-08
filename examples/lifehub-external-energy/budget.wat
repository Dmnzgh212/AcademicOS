(module
  (import "lifehub" "call_interface_json"
    (func $get_spend (param i32 i32 i32 i32 i32 i32) (result i32)))
  (memory (export "memory") 1)
  (data (i32.const 0) "lab.energy.spent@1")
  (data (i32.const 64) "{}")
  (func (export "run") (result i32)
    (local $pos i32)
    (local $spent i32)
    (if (i32.ne
      (call $get_spend (i32.const 0) (i32.const 18)
        (i32.const 64) (i32.const 2)
        (i32.const 128) (i32.const 128))
      (i32.const 18))
      (then unreachable))
    (local.set $pos (i32.const 138))
    (loop $parse
      (local.set $spent
        (i32.add
          (i32.mul (local.get $spent) (i32.const 10))
          (i32.sub (i32.load8_u (local.get $pos)) (i32.const 48))))
      (local.set $pos (i32.add (local.get $pos) (i32.const 1)))
      (br_if $parse (i32.lt_u (local.get $pos) (i32.const 144))))
    (if (result i32) (i32.ge_u (local.get $spent) (i32.const 200))
      (then (i32.const 0))
      (else (i32.sub (i32.const 200) (local.get $spent)))))
)