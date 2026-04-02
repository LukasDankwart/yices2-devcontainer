import z3
from z3 import *

def z3_abs(x):
    return z3.If(x >= 0, x, -x)


def extract_mbp_core(expr, f_model, r_substitution):
    """
    Traverses through the AST tree and extracts path that is 'TRUE' by given model

    :param expr: original formular (expression)
    :param f_model: model with assignment for y variable
    :param r_substitution: current values for r to substitute

    :return: linear expression of the AST with only active paths included for given r
    """
    path_conditions = []

    # Recursively traverse through the AST
    def traverse(e):
        # In this case current node is a leaf
        if not z3.is_app(e):
            return e

        decl = e.decl()
        # In this case, we are at a ITE node
        if decl.kind() == z3.Z3_OP_ITE:
            # If, then, else expressions
            cond, then_expr, else_expr = e.children()

            # Check 'If' condition to be true for current r
            cond_with_r = z3.substitute(cond, *r_substitution)
            cond_val = f_model.eval(cond_with_r, model_completion=True)

            # 'If' condition is true, so THEN is 'executed'
            if z3.is_true(cond_val):
                # Path to 'THEN' branch is stored
                path_conditions.append(traverse(cond))
                # We traverse into 'THEN' branch
                return traverse(then_expr)
            # 'If' condition is false, so ELSE branch is 'executed'
            else:
                # Path to 'ELSE' branch is stored (ensure that 'IF' is not true for next F-solver iteration)
                path_conditions.append(z3.Not(traverse(cond)))
                # We traverse into the 'ELSE' branch
                return traverse(else_expr)
        else:
            # Otherwise dive into all children nodes
            children = [traverse(c) for c in e.children()]
            return decl(*children)

    # Linear expression of the AST, where ReLU branches have been replaced by their branch which is active for current r
    linear_expr = traverse(expr)

    return z3.And(linear_expr, *path_conditions)


def main():
    concrete_input = [
        -0.021025,
        -1.043187,
        0.300265,
        0.570702,
        -1.124416,
        -1.794718,
        0.569139,
        -0.361468
    ]

    # Path to SMT of network
    path = "z3_examples/gen_examples/z3_gen_fixed.smt2"
    formulas = z3.parse_smt2_file(path)
    """
    formulas[0] : y lower bound
    formulas[1] : y upper bound
    formulas[2] : f1(r, y) >= f0(r,y)
    """

    # Initialize Solvers
    e_solver = z3.Optimize()
    f_solver = z3.Solver()

    # Setup solvers
    # E-Optimizer: minimize distances | r_i - x_i | (y remains unknown)
    r_vars = [z3.Real(f"r{i}") for i in range(7)]
    d_vars = [z3.Real(f"d{i}") for i in range(len(r_vars))]
    # Define L1 distance for each variable
    for (idx, (r_var, d_var)) in enumerate(zip(r_vars, d_vars)):
        #e_solver.add(d_var >= r_var - concrete_input[idx])
        #e_solver.add(d_var >= concrete_input[idx] - r_var)
        e_solver.add(d_var >= r_var)
        e_solver.add(d_var >= -r_var)
    l1_norm_objective = z3.Sum(d_vars)
    e_solver.minimize(l1_norm_objective)

    # F-Solver: find y that breaks pre-condition => post-condition
    y_var = z3.Real("y")
    lb_cond_y = formulas[0]
    ub_cond_y = formulas[1]
    post_cond = formulas[2]
    f_solver.add(lb_cond_y)
    f_solver.add(ub_cond_y)

    gen_constraints = []
    iteration = 1
    while True:
        print(f"Iteration {iteration} started..")

        # Variant with new initialization of E-Optimizer ever iteration
        e_solver = z3.Optimize()
        for (idx, (r_var, d_var)) in enumerate(zip(r_vars, d_vars)):
            # e_solver.add(d_var >= r_var - concrete_input[idx])
            # e_solver.add(d_var >= concrete_input[idx] - r_var)
            e_solver.add(d_var >= r_var)
            e_solver.add(d_var >= -r_var)
        l1_norm_objective = z3.Sum(d_vars)
        obj_handle = e_solver.minimize(l1_norm_objective)
        for gen_constraint in gen_constraints:
            e_solver.add(gen_constraint)

        if e_solver.check() == z3.sat:
            e_model = e_solver.model()

            print(f"Z3 obj: {obj_handle.value()}")

            current_r_vals = [e_model.eval(r, model_completion=True) for r in r_vars]
            r_floats = [float(val.as_fraction()) if z3.is_rational_value(val) else val.approx(10) for val in
                        current_r_vals]
            print(f"E-Solver predicts: r = {r_floats}")

            current_l1 = e_model.eval(l1_norm_objective, model_completion=True)
            print(f"Current L1-Norm (Costs): {float(current_l1.as_fraction())}")
        else:
            print(f"UNSAT: E-Solver couldn't find candidates for r!")

        # Save last state of F-Solver:
        f_solver.push()
        r_substitution = list(zip(r_vars, current_r_vals))
        r_formula = post_cond
        formula_substituted = z3.substitute(r_formula, *r_substitution)
        f_solver.add(z3.Not(formula_substituted))

        if f_solver.check() == z3.sat:
            f_model = f_solver.model()
            y_counter_example = f_model.eval(y_var, model_completion=True)
            print(f"F-Solver found counter example: y = {y_counter_example}")

            error_formula = z3.And(lb_cond_y, ub_cond_y, z3.Not(post_cond))
            linear_core = extract_mbp_core(error_formula, f_model, r_substitution)

            exists_error = z3.Exists([y_var], linear_core)
            mbp_tactic = z3.Then(z3.Tactic("simplify"), z3.Tactic("qe"))

            try:
                bad_space_r = mbp_tactic(exists_error).as_expr()
                gen_constraint = z3.Not(bad_space_r)
                #e_solver.add(gen_constraint)
                gen_constraints.append(gen_constraint)
                print(f"-> MPB successful! New gen constraint added to E-solver. \n")
            except z3.Z3Exception as e:
                print(f"-> Error while doing MBP: {e}")

        else: # F-Solver calls UNSAT
            print(f"\n UNSAT! F-Solver couldn't find counter example.")
            print(f"Optimal Counterfactual r = {r_floats}")
            print(f"Number of general constraints: {len(gen_constraints)}")
            print(f"\n Start verification of r being valid for all y: ")
            verifier = z3.Solver()
            final_r_subs = list(zip(r_vars, current_r_vals))
            substitution = z3.substitute(post_cond, *final_r_subs)
            verifier.add(lb_cond_y, ub_cond_y)
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


if __name__ == "__main__":
    main()


