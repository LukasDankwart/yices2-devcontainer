import csv
import random
from z3_utils import *
import pandas as pd

def z3_reasoning(onnx_path, input_path):
    # Get a concrete input and its original prediction by the onnx model
    concrete_inputs = parse_concrete_inputs(input_path)

    results = []
    for idx in range(len(concrete_inputs)):
        # Define random missing input (y) and fetch concrete input
        concrete_input = concrete_inputs[idx]
        gt_class = concrete_input[-1]
        num_inputs = len(concrete_input[:-1])
        rand_missing_input = random.choice([i for i in range(num_inputs)])

        # Get output-var names and z3 expressions for every output of the onnx model
        output_vars, output_formulas = onnx2z3(onnx_path)

        num_classes = len(output_vars)
        rand_target_class = random.choice([i for i in range(num_classes) if i != gt_class])

        r_optim, target_class, cost, iterations = z3_ef_variant(
            rand_missing_input, rand_target_class, concrete_input[:-1], output_vars, output_formulas
        )

        cx = []
        for (j, val) in enumerate(r_optim):
            cx.append(val)
            if j == target_class - 1:
                cx.append("y")
        results.append([*cx, target_class, float(cost.as_fraction()), iterations])

    columns_a = [f"orig_inp{i}" for i in range(len(concrete_inputs[0][:-1]))] + ["orig_class"]
    columns_b = [f"r{i}" for i in range(len(concrete_inputs[0][:-1]))] + ["target_class"] + ["cost"] + ["iterations"]

    df_A = pd.DataFrame(concrete_inputs, columns=columns_a)
    df_B = pd.DataFrame(results, columns=columns_b)

    df_combined = pd.concat([df_A, df_B], axis=1)
    results_path = input_path.removesuffix(".csv") + "_cx.csv"
    df_combined.to_csv(results_path, index=False, sep=";")


def z3_ef_variant(missing_input_idx, target_class, concrete_input, output_vars, output_formulas):

    assert len(output_vars) == len(output_formulas), "Output var-keys should have same amount as output formulas!"
    assert len(output_formulas) > 0, "Network encoding is expected to have at least one output neuron/formula!"

    # Get original name of missing input and replace it with 'y' as simple convention in every expression
    original_name = output_formulas[output_vars[0]]["vars"][missing_input_idx]
    if original_name is None:
        raise RuntimeError(f"Given desired index for missing input '{missing_input_idx}' might be out of bounds!")

    # Perform substitution, that missing input var name equals "y", all others will be r0, ..., rN
    original_vars = output_formulas[output_vars[0]]["vars"]
    new_vars = []
    r_vars = []
    y_var = z3.Real("y")
    for (idx, orig_var) in enumerate(original_vars):
        if idx != missing_input_idx:
            r_var = z3.Real(f"r{idx}")
            r_vars.append(r_var)
            new_vars.append(r_var)
        else:
            new_vars.append(y_var)
    var_mapping = list(zip(original_vars, new_vars))
    for output_var in output_vars:
        output_formulas[output_var]["vars"][missing_input_idx] = "y"
        output_formulas[output_var]["expr"] = z3.substitute(output_formulas[output_var]["expr"], var_mapping)

    # Initialize Solvers
    e_solver = z3.Optimize()
    f_solver = z3.Solver()

    # Setup Solvers
    # E-Optimizer (only vars since it is initialized in every loop iteration):
    d_vars = [z3.Real(f"d{i}") for i in range(len(r_vars))]
    for (idx, (r_var, d_var)) in enumerate(zip(r_vars, d_vars)):
        e_solver.add(d_var >= r_var)
        e_solver.add(d_var >= -r_var)
    l1_norm_objective = z3.Sum(d_vars)
    e_solver.minimize(l1_norm_objective)

    # F-Solver:
    lb_y = y_var >= -1
    ub_y = y_var <= 1
    f_solver.add(lb_y)
    f_solver.add(ub_y)

    # Build input mapping: input_var + concrete_input (but "y" is excluded from this mapping!
    r_vars_offset = []
    for (idx, concrete_val) in enumerate(concrete_input):
        if idx != missing_input_idx:
            r = new_vars[idx]
            r_vars_offset.append((r + concrete_val))
    assert len(r_vars_offset) == len(r_vars), "Number of concrete vals for 'r' and number of r vars should be equal!"
    r_conc_mapping = list(zip(r_vars, r_vars_offset))

    # Build post-condition: output[target_class] >= every other output
    target_class_expr = output_formulas[output_vars[target_class]]["expr"]
    target_class_expr = z3.substitute(target_class_expr, r_conc_mapping)
    if target_class_expr is None:
        raise RuntimeError(f"Expression couldn't be fetched for specified target class!")
    post_cond = z3.And(True)
    for (idx, output_var_name) in enumerate(output_vars):
        if idx != target_class:
            expr = output_formulas[output_var_name]["expr"]
            post_cond = z3.And(post_cond, (target_class_expr >= z3.substitute(expr, r_conc_mapping)))

    generalized_constraints = []
    iteration = 1
    while True:
        print(f"\n Iteration {iteration} started..")

        print(f"Call (E-Solver) optimization...")
        # Variant with new initialization of E-Optimizer ever iteration
        e_solver = z3.Optimize()
        for (idx, (r_var, d_var)) in enumerate(zip(r_vars, d_vars)):
            e_solver.add(d_var >= r_var)
            e_solver.add(d_var >= -r_var)
        l1_norm_objective = z3.Sum(d_vars)
        obj_handle = e_solver.minimize(l1_norm_objective)
        for gen_constraint in generalized_constraints:
            e_solver.add(gen_constraint)

        if e_solver.check() == z3.sat:
            e_model = e_solver.model()
            print(f"Z3 obj: {obj_handle.value()}")
            current_r_vals = [e_model.eval(r, model_completion=True) for r in r_vars]
            r_floats = [float(val.as_fraction()) if z3.is_rational_value(val) else val.approx(10) for val in
                        current_r_vals]
            print(f"E-Solver predicts: r = {r_floats}")
            current_l1 = e_model.eval(l1_norm_objective, model_completion=True)
            print(f"Current L1-Norm (Costs): {float(current_l1.as_fraction())} \n")

        # Save last state of F-Solver:
        f_solver.push()
        r_substitution = list(zip(r_vars, current_r_vals))
        r_formula = post_cond
        formula_substituted = z3.substitute(r_formula, *r_substitution)
        f_solver.add(z3.Not(formula_substituted))
        print("Call (F-Solver) for current r...")
        if f_solver.check() == z3.sat:
            f_model = f_solver.model()
            y_counter_example = float(f_model.eval(y_var, model_completion=True).as_fraction())
            print(f"F-Solver found counter example: y = {y_counter_example}")

            error_formula = z3.And(lb_y, ub_y, z3.Not(post_cond))
            linear_core = extract_mbp_core(error_formula, f_model, r_substitution)

            exists_error = z3.Exists([y_var], linear_core)
            mbp_tactic = z3.Then(z3.Tactic("simplify"), z3.Tactic("qe"))

            try:
                bad_space_r = mbp_tactic(exists_error).as_expr()
                gen_constraint = z3.Not(bad_space_r)
                generalized_constraints.append(gen_constraint)
                gen_constraint_validation(generalized_constraints, r_substitution)
                print(f"-> MPB successful! New gen constraint added to E-solver. \n")
            except z3.Z3Exception as e:
                print(f"-> Error while doing MBP: {e}")

        else: # F-Solver calls UNSAT
            print(f"\n UNSAT! F-Solver couldn't find counter example.")
            print(f"Optimal Counterfactual r = {r_floats}")
            print(f"Number of general constraints: {len(generalized_constraints)}")
            print(f"\n Start verification of r being valid for all y: ")
            verifier = z3.Solver()
            final_r_subs = list(zip(r_vars, current_r_vals))
            substitution = z3.substitute(post_cond, *final_r_subs)
            verifier.add(lb_y, ub_y)
            verifier.add(z3.Not(substitution))
            result = verifier.check()
            if result == z3.unsat:
                print(f"Correctness of r was verified!")
            else:
                print(f"Verification failed. Verifier has found a counter example for y.")
                print(f"y = {float(verifier.model().eval(y_var).as_fraction())}")
            break

        f_solver.pop()
        iteration += 1

    return r_floats, target_class, current_l1, iteration


def parse_concrete_inputs(csv_path):
    lines = []
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=',')
        header = next(reader)
        for line in reader:
            float_line = [float(x) for x in line]
            lines.append(float_line)
    return lines


if __name__ == "__main__":
    onnx_path = "main/networks/concrete/flow.onnx"
    input_path = "main/networks/concrete/flow_examples.csv"
    z3_reasoning(onnx_path, input_path)