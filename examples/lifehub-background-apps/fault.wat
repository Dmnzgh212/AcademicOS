;; Controlled fault injection, not claimed as a third real application.
(module
  (memory (export "memory") 1)
  (global $turns (mut i32) (i32.const 0))
  (func (export "ready") (result i32) i32.const 1)
  (func (export "tick") (result i32)
    (global.set $turns (i32.add (global.get $turns) (i32.const 1)))
    (i32.ge_u (global.get $turns) (i32.const 3)))
  (func (export "run") (result i32) unreachable))
