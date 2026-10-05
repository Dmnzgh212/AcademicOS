(module
  (import "lifehub" "call_service_json"
    (func $call (param i32 i32 i32 i32 i32 i32) (result i32)))
  (memory (export "memory") 1)
  (data (i32.const 0) "example.echo:echo")
  (data (i32.const 64) "{\22message\22:\22hello from Wasm\22}")
  (func (export "run") (result i32)
    (call $call (i32.const 0) (i32.const 17)
                (i32.const 64) (i32.const 29)
                (i32.const 128) (i32.const 4096))))
