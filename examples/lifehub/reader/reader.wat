(module
  (import "lifehub" "read_json"
    (func $read (param i32 i32 i32 i32) (result i32)))
  (memory (export "memory") 1)
  (data (i32.const 0) "sample.records")
  (func (export "run") (result i32)
    (call $read (i32.const 0) (i32.const 14)
                (i32.const 128) (i32.const 4096))))
