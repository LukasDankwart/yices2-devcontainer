import utils
from subprocesses.utils import run_yices_on_smt, parse_yices_results

if __name__ == "__main__":
    smt_path = "subprocesses/ef/classifier_medium_ef.smt2"

    results = run_yices_on_smt(smt_path)
    res_vars = ["r0", "r1", "r2", "r3", "r4", "r5", "r6"]
    results = parse_yices_results(results, res_vars, [])

    # Das ist der original input, anhand welcher ef/classifier_medium_ef.smt2 manuell formuliert wurde
    x_input = [
        -0.021025,
        -1.043187,
        0.300265,
        0.570702,
        -1.124416,
        -1.794718,
        0.569139,
        -0.361468  # y set to lb
    ]
    for res_var in res_vars:
        print(results["model"].get(res_var))

    # TODO: Verifizieren, dass ONNX Runtime auf dem Input wirklich klasse 1 und nicht 0 predicted

