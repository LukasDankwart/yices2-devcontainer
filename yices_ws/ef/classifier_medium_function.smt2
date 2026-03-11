(set-logic LRA)
; --- Function for Output 0 ---
(define-fun run_network_out_0 ((onnx__MatMul_0_0 Real) (onnx__MatMul_0_1 Real) (onnx__MatMul_0_2 Real) (onnx__MatMul_0_3 Real) (onnx__MatMul_0_4 Real) (onnx__MatMul_0_5 Real) (onnx__MatMul_0_6 Real) (onnx__MatMul_0_7 Real)) Real
  (let ((_fc1_MatMul_output_0_0 (+ (+ (* 0.298401 onnx__MatMul_0_0) (* (- 0.170765) onnx__MatMul_0_1) (* (- 0.274465) onnx__MatMul_0_2) (* (- 0.083906) onnx__MatMul_0_3) (* (- 0.297085) onnx__MatMul_0_4) (* (- 0.077657) onnx__MatMul_0_5) (* (- 0.135193) onnx__MatMul_0_6) (* 0.009620 onnx__MatMul_0_7)) 0.000000)))
   (let ((_fc1_MatMul_output_0_1 (+ (+ (* 1.230528 onnx__MatMul_0_0) (* 0.576013 onnx__MatMul_0_1) (* 0.155027 onnx__MatMul_0_2) (* (- 0.861319) onnx__MatMul_0_3) (* 0.710167 onnx__MatMul_0_4) (* (- 0.094297) onnx__MatMul_0_5) (* (- 0.461752) onnx__MatMul_0_6) (* 2.522396 onnx__MatMul_0_7)) 0.000000)))
    (let ((_fc1_MatMul_output_0_2 (+ (+ (* (- 0.223662) onnx__MatMul_0_0) (* 0.157640 onnx__MatMul_0_1) (* (- 0.277250) onnx__MatMul_0_2) (* (- 0.332041) onnx__MatMul_0_3) (* (- 0.119962) onnx__MatMul_0_4) (* (- 0.004430) onnx__MatMul_0_5) (* 0.208340 onnx__MatMul_0_6) (* 0.107654 onnx__MatMul_0_7)) 0.000000)))
     (let ((_fc1_MatMul_output_0_3 (+ (+ (* 0.108714 onnx__MatMul_0_0) (* (- 0.280222) onnx__MatMul_0_1) (* 0.048441 onnx__MatMul_0_2) (* (- 0.004711) onnx__MatMul_0_3) (* (- 0.144241) onnx__MatMul_0_4) (* 0.195717 onnx__MatMul_0_5) (* (- 0.097849) onnx__MatMul_0_6) (* (- 0.040117) onnx__MatMul_0_7)) 0.000000)))
      (let ((_fc1_Add_output_0_0 (+ (- 0.302294) _fc1_MatMul_output_0_0)))
       (let ((_fc1_Add_output_0_1 (+ 0.203366 _fc1_MatMul_output_0_1)))
        (let ((_fc1_Add_output_0_2 (+ (- 0.136880) _fc1_MatMul_output_0_2)))
         (let ((_fc1_Add_output_0_3 (+ (- 0.310783) _fc1_MatMul_output_0_3)))
          (let ((_Relu_output_0_0 (ite (> _fc1_Add_output_0_0 0.0) _fc1_Add_output_0_0 0.0)))
           (let ((_Relu_output_0_1 (ite (> _fc1_Add_output_0_1 0.0) _fc1_Add_output_0_1 0.0)))
            (let ((_Relu_output_0_2 (ite (> _fc1_Add_output_0_2 0.0) _fc1_Add_output_0_2 0.0)))
             (let ((_Relu_output_0_3 (ite (> _fc1_Add_output_0_3 0.0) _fc1_Add_output_0_3 0.0)))
              (let ((_fc2_MatMul_output_0_0 (+ (+ (* 0.207848 _Relu_output_0_0) (* (- 2.105881) _Relu_output_0_1) (* 0.034236 _Relu_output_0_2) (* 0.128429 _Relu_output_0_3)) 0.000000)))
               (let ((_fc2_MatMul_output_0_1 (+ (+ (* (- 0.465517) _Relu_output_0_0) (* 2.395455 _Relu_output_0_1) (* 0.487521 _Relu_output_0_2) (* 0.225442 _Relu_output_0_3)) 0.000000)))
                (let ((v_11_0 (+ 1.040617 _fc2_MatMul_output_0_0)))
                 (let ((v_11_1 (+ (- 1.674182) _fc2_MatMul_output_0_1)))
                  v_11_0
)))))))))))))))))

; --- Function for Output 1 ---
(define-fun run_network_out_1 ((onnx__MatMul_0_0 Real) (onnx__MatMul_0_1 Real) (onnx__MatMul_0_2 Real) (onnx__MatMul_0_3 Real) (onnx__MatMul_0_4 Real) (onnx__MatMul_0_5 Real) (onnx__MatMul_0_6 Real) (onnx__MatMul_0_7 Real)) Real
  (let ((_fc1_MatMul_output_0_0 (+ (+ (* 0.298401 onnx__MatMul_0_0) (* (- 0.170765) onnx__MatMul_0_1) (* (- 0.274465) onnx__MatMul_0_2) (* (- 0.083906) onnx__MatMul_0_3) (* (- 0.297085) onnx__MatMul_0_4) (* (- 0.077657) onnx__MatMul_0_5) (* (- 0.135193) onnx__MatMul_0_6) (* 0.009620 onnx__MatMul_0_7)) 0.000000)))
   (let ((_fc1_MatMul_output_0_1 (+ (+ (* 1.230528 onnx__MatMul_0_0) (* 0.576013 onnx__MatMul_0_1) (* 0.155027 onnx__MatMul_0_2) (* (- 0.861319) onnx__MatMul_0_3) (* 0.710167 onnx__MatMul_0_4) (* (- 0.094297) onnx__MatMul_0_5) (* (- 0.461752) onnx__MatMul_0_6) (* 2.522396 onnx__MatMul_0_7)) 0.000000)))
    (let ((_fc1_MatMul_output_0_2 (+ (+ (* (- 0.223662) onnx__MatMul_0_0) (* 0.157640 onnx__MatMul_0_1) (* (- 0.277250) onnx__MatMul_0_2) (* (- 0.332041) onnx__MatMul_0_3) (* (- 0.119962) onnx__MatMul_0_4) (* (- 0.004430) onnx__MatMul_0_5) (* 0.208340 onnx__MatMul_0_6) (* 0.107654 onnx__MatMul_0_7)) 0.000000)))
     (let ((_fc1_MatMul_output_0_3 (+ (+ (* 0.108714 onnx__MatMul_0_0) (* (- 0.280222) onnx__MatMul_0_1) (* 0.048441 onnx__MatMul_0_2) (* (- 0.004711) onnx__MatMul_0_3) (* (- 0.144241) onnx__MatMul_0_4) (* 0.195717 onnx__MatMul_0_5) (* (- 0.097849) onnx__MatMul_0_6) (* (- 0.040117) onnx__MatMul_0_7)) 0.000000)))
      (let ((_fc1_Add_output_0_0 (+ (- 0.302294) _fc1_MatMul_output_0_0)))
       (let ((_fc1_Add_output_0_1 (+ 0.203366 _fc1_MatMul_output_0_1)))
        (let ((_fc1_Add_output_0_2 (+ (- 0.136880) _fc1_MatMul_output_0_2)))
         (let ((_fc1_Add_output_0_3 (+ (- 0.310783) _fc1_MatMul_output_0_3)))
          (let ((_Relu_output_0_0 (ite (> _fc1_Add_output_0_0 0.0) _fc1_Add_output_0_0 0.0)))
           (let ((_Relu_output_0_1 (ite (> _fc1_Add_output_0_1 0.0) _fc1_Add_output_0_1 0.0)))
            (let ((_Relu_output_0_2 (ite (> _fc1_Add_output_0_2 0.0) _fc1_Add_output_0_2 0.0)))
             (let ((_Relu_output_0_3 (ite (> _fc1_Add_output_0_3 0.0) _fc1_Add_output_0_3 0.0)))
              (let ((_fc2_MatMul_output_0_0 (+ (+ (* 0.207848 _Relu_output_0_0) (* (- 2.105881) _Relu_output_0_1) (* 0.034236 _Relu_output_0_2) (* 0.128429 _Relu_output_0_3)) 0.000000)))
               (let ((_fc2_MatMul_output_0_1 (+ (+ (* (- 0.465517) _Relu_output_0_0) (* 2.395455 _Relu_output_0_1) (* 0.487521 _Relu_output_0_2) (* 0.225442 _Relu_output_0_3)) 0.000000)))
                (let ((v_11_0 (+ 1.040617 _fc2_MatMul_output_0_0)))
                 (let ((v_11_1 (+ (- 1.674182) _fc2_MatMul_output_0_1)))
                  v_11_1
)))))))))))))))))

; --- Network Functions Defined ---

; --- Defining EF formulation
(declare-fun r0 () Real)
(declare-fun r1 () Real)
(declare-fun r2 () Real)
(declare-fun r3 () Real)
(declare-fun r4 () Real)
(declare-fun r5 () Real)
(declare-fun r6 () Real)
(declare-fun r7 () Real)
(assert
  (forall ((y Real))
    (=>
      (and (>=y (-1.0)) and (<= y 1.0))
      ( >
        (run_network_out_1
           (+ (- 0.021025) r)
           (+ (- 1.043187) r)
           (+ 0.300265 r
           (+ 0.570702 r)
           (+ (- 1.124416) r)
           (+ (- 1.794718) r)
           (+ 0.569139 r)
           y
        )
        (run_network_out_0
           (+ (- 0.021025) r)
           (+ (- 1.043187) r)
           (+ 0.300265 r
           (+ 0.570702 r)
           (+ (- 1.124416) r)
           (+ (- 1.794718) r)
           (+ 0.569139 r)
           y
        )
      )
    )
  )
)
