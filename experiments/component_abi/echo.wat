(component
  (core module $implementation
    (func (export "echo") (param i32) (result i32) local.get 0))
  (core instance $instance (instantiate $implementation))
  (func $echo (param "value" u32) (result u32)
    (canon lift (core func $instance "echo")))
  (export "echo" (func $echo)))
