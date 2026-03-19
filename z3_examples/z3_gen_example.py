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
    # Path to SMT of network
    path = "z3_examples/gen_examples/z3_gen.smt2"
    parsed_formulas = z3.parse_smt2_file(path)

    original_phi = parsed_formulas[0]

    # Reference variables in python
    r_vars = [z3.Real(f'r{i}') for i in range(7)]
    y = z3.Real('y')

    # Initialize solvers
    e_solver = z3.Optimize()
    f_solver = z3.Solver()

    # Variant with help variables t representing the abs
    """
    t_vars = [z3.Real(f't{i}') for i in range(7)]
    for r, t in zip(r_vars, t_vars):
        e_solver.add(t >= r)
        e_solver.add(t >= -r)
    l1_norm_objective = z3.Sum(t_vars)
    """
    l1_norm_objective = z3.Sum([z3_abs(r) for r in r_vars])
    e_solver.minimize(l1_norm_objective)

    iteration = 1
    while True:
        print(f"\n Iteration {iteration} started")

        if e_solver.check() == z3.sat:
            e_model = e_solver.model()

            current_r_vals = [e_model.eval(r, model_completion=True) for r in r_vars]

            r_floats = [float(val.as_fraction()) if z3.is_rational_value(val) else 0.0 for val in current_r_vals]
            print(f"E-Solver predicts: r = {r_floats}")

            current_l1 = e_model.eval(l1_norm_objective, model_completion=True)
            print(f"Current L1-Norm (Costs): {float(current_l1.as_fraction())}")
        else:
            print(f"UNSAT! No CX found for implicant: {original_phi}")
            break

        # Save last state of F-Solver
        f_solver.push()

        # Defines substitution from r0 -> assignment of r0 .... for all r vars
        r_substitution = list(zip(r_vars, current_r_vals))

        phi_with_current_r = z3.substitute(original_phi, *r_substitution)

        f_solver.add(z3.Not(phi_with_current_r))

        if f_solver.check() == z3.sat:
            f_model = f_solver.model()
            bad_y_val = f_model.eval(y, model_completion=True)
            print(f"F-Solver found Counterexample: y = {float(bad_y_val.as_fraction())}")

            error_formula = z3.Not(original_phi)
            linear_core = extract_mbp_core(error_formula, f_model, r_substitution)

            exists_error = z3.Exists([y], linear_core)
            mbp_tactic = z3.Then(z3.Tactic('simplify'), z3.Tactic('qe'))

            try:
                bad_space_for_r = mbp_tactic(exists_error).as_expr()
                gen_constraint = z3.Not(bad_space_for_r)
                e_solver.add(gen_constraint)
                print(f"-> MBP successful! New gen constraint was added.")

            except z3.Z3Exception as e:
                print(f"-> Z3 error while MBP: {e}")
        else:
            print(f"\n UNSAT! F-Solver couldn't find counter example.")
            print(f"Optimal Counterfactual r = {r_floats}")
            print(f"\n Start verification of r being valid for all y: ")
            verifier = z3.Solver()
            final_r_subs = [(r_vars[i], z3.RealVal(r_floats[i])) for i in range(7)]
            phi_verified = z3.substitute(original_phi, *final_r_subs)
            verifier.add(y >= -1.0, y <= 1.0)
            verifier.add(z3.Not(phi_verified))
            result = verifier.check()
            if result == z3.unsat:
                print(f"Correctness of r was verified!")
            else:
                print(f"Verification failed. Verifier has found a counter example for y.")
                print(f"y = {float(verifier.model().eval(y).as_fraction())}")
            break

        f_solver.pop()
        iteration += 1


if __name__ == "__main__":
    main()