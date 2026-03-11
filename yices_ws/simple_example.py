import subprocess


def test():
    smt_code = """
        (set-logic LIA)
        (declare-fun x () Int)
        (declare-fun y () Int)
        (assert (exists ((x Int) (y Int)) (and (> y 0) (= (- y x) 0) (not (= y x)))))
        (check-sat)
        """

    results = subprocess.run(
        ['yices_ws-smt2'],
        input=smt_code,
        text=True,
        capture_output=True,
    )

    print("Response from YICES2 EF-Solver: ")
    print(results.stdout.strip())

def adv_example():
    smt_code = """
        (set-logic LIA)
        ; --- Input var (we bound x to be greater than 0)
        (declare-fun x () Int)
        (assert (>= x 2))
        (assert (<= x 2))
        ; --- Weights and set weights
        (define-fun w1 () Int (- 1))
        (define-fun w2 () Int 1)
        (define-fun w3 () Int (- 1))
        (define-fun w4 () Int 1)
        ; --- Define Exists/ForAll expression
        (assert 
          (exists ((r1 Int) (r2 Int)) 
            (forall ((y Int)) 
              ; If y >= 0 
              (=> (>= y 0)
                (> 
                  ; Das ist t2: (* (+ (* (+ x r1) w1) (* (+ y r2) w2)) w4)
                  (* (+ (* (+ x r1) w1) (* (+ y r2) w2)) w4) 
                  
                  ; Das ist t1: (* (+ (* (+ x r1) w1) (* (+ y r2) w2)) w3)
                  (* (+ (* (+ x r1) w1) (* (+ y r2) w2)) w3)
                )
              )
            )
          )
        )
        (check-sat)
        (exit)
    """

    results = subprocess.run(
        ['yices_ws-smt2'],
        input=smt_code,
        text=True,
        capture_output=True,
    )

    print("Response from YICES2 EF-Solver: ")
    print(results.stdout.strip())


if __name__ == "__main__":
    adv_example()