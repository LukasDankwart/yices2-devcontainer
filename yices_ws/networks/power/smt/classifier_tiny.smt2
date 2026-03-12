(set-logic LRA)
 
(define-fun OutputNeuron_0_idx0 ((onnx__MatMul_0_0 Real) (onnx__MatMul_0_1 Real) (onnx__MatMul_0_2 Real) (onnx__MatMul_0_3 Real)) Real
  (+ (- (/ 1008249.0 250000.0))
   (* (/ 867617.0 125000.0) onnx__MatMul_0_0)
   (* (/ 81804.0 15625.0) onnx__MatMul_0_1)
   (* (- (/ 411137.0 100000.0)) onnx__MatMul_0_2)
   (* (- (/ 225181.0 1000000.0)) onnx__MatMul_0_3))
)

(define-fun OutputNeuron_0_idx1 ((onnx__MatMul_0_0 Real) (onnx__MatMul_0_1 Real) (onnx__MatMul_0_2 Real) (onnx__MatMul_0_3 Real)) Real
  (+ (/ 400079.0 100000.0)
   (* (- (/ 6875531.0 1000000.0)) onnx__MatMul_0_0)
   (* (- (/ 2821071.0 500000.0)) onnx__MatMul_0_1)
   (* (/ 376427.0 100000.0) onnx__MatMul_0_2)
   (* (- (/ 88519.0 1000000.0)) onnx__MatMul_0_3))
)

