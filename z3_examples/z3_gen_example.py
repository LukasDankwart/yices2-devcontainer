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
    path = "z3_examples/gen_examples/z3_gen_fixed.smt2"
    parsed_formulas = z3.parse_smt2_file(path)

    #original_phi = parsed_formulas[0]
    original_phi = parsed_formulas

    # Reference variables in python
    r_vars = [z3.Real(f'r{i}') for i in range(7)]
    y = z3.Real('y')

    # Initialize solvers
    e_solver = z3.Optimize()
    f_solver = z3.Solver()

    # Setup E-Solver
    e_solver = z3.Optimize()
    d_vars = [z3.Real(f'd_{i}') for i in range(len(r_vars))]
    for r, d in zip(r_vars, d_vars):
        e_solver.add(d >= r)
        e_solver.add(d >= -r)
    l1_norm_objective = z3.Sum(d_vars)
    obj_handle = e_solver.minimize(l1_norm_objective)
    e_solver.add(original_phi)

    # Setup F-Solver
    print(f"Original phi 0: {original_phi[0]}")
    print(f"Original phi 1: {original_phi[1]}")
    f_solver.add(original_phi[0])
    f_solver.add(original_phi[1])

    # Variant with help variables t representing the abs
    """
    t_vars = [z3.Real(f't{i}') for i in range(7)]
    for r, t in zip(r_vars, t_vars):
        e_solver.add(t >= r)
        e_solver.add(t >= -r)
    l1_norm_objective = z3.Sum(t_vars)
    """

    # Objective variant 1
    """
    l1_norm_objective = z3.Sum([z3_abs(r) for r in r_vars])
    e_solver.minimize(l1_norm_objective)
    """

    # Objective variant 2
    d_vars = [z3.Real(f'd_{i}') for i in range(len(r_vars))]
    for r, d in zip(r_vars, d_vars):
        e_solver.add(d >= r)
        e_solver.add(d >= -r)
    l1_norm_objective = z3.Sum(d_vars)
    e_solver.minimize(l1_norm_objective)

    last_gens = []
    last_dist = []

    iteration = 1
    while True:
        print(f"\n Iteration {iteration} started")

        if e_solver.check() == z3.sat:
            e_model = e_solver.model()

            current_r_vals = [e_model.eval(r, model_completion=True) for r in r_vars]
            current_y = float(e_model.eval(y).as_fraction())
            print(f"CURRENT y for Model: {current_y}")

            r_floats = [float(val.as_fraction()) if z3.is_rational_value(val) else val.approx(10) for val in current_r_vals]
            print(f"E-Solver predicts: r = {r_floats}")

            current_l1 = e_model.eval(l1_norm_objective, model_completion=True)
            print(f"Current L1-Norm (Costs): {float(current_l1.as_fraction())}")
            last_dist.append(float(current_l1.as_fraction()))

            #current_l1 = obj_handle.value()
            #if not (z3.is_int_value(current_l1) or z3.is_rational_value(current_l1) or z3.is_arith(current_l1)):
            #    current_l1 = current_l1.approx(10)
            #print(f"Current L1-Norm (Costs): {current_l1}")

            last_dist.append(current_l1)

        else:
            print(f"UNSAT! No CX found for implicant: {original_phi}")
            break

        # Save last state of F-Solver
        f_solver.push()

        # Defines substitution from r0 -> assignment of r0 .... for all r vars
        r_substitution = list(zip(r_vars, current_r_vals))

        r_formula = original_phi[2]
        phi_with_current_r = z3.substitute(r_formula, *r_substitution)

        f_solver.add(z3.Not(phi_with_current_r))

        if f_solver.check() == z3.sat:
            f_model = f_solver.model()
            bad_y_val = f_model.eval(y, model_completion=True)
            print(f"F-Solver found Counterexample: y = {float(bad_y_val.as_fraction())}")

            # TODO: Hier darf nur das Subformula übergeben werden, aus dem der Kern bestimmt werden soll (f1 >= f0)!
            #error_formula = z3.Not(original_phi)
            #error_formula = z3.And(original_phi[0], original_phi[1], z3.Not(original_phi[2]))
            error_formula = z3.Not(original_phi[2])
            linear_core = extract_mbp_core(error_formula, f_model, r_substitution)

            exists_error = z3.Exists([y], linear_core)
            mbp_tactic = z3.Then(z3.Tactic('simplify'), z3.Tactic('qe'))

            try:
                bad_space_for_r = mbp_tactic(exists_error).as_expr()
                gen_constraint = z3.Not(bad_space_for_r)
                e_solver.add(gen_constraint)
                print(f"-> MBP successful! New gen constraint was added.")
                last_gens.append(gen_constraint)
                """
                if len(last_dist) >= 2 and last_dist[-1] < last_dist[-2]:
                    print(f"previous gen constraint: {last_gens[-2]}")
                    print(f"new gen constraint: {last_gens[-1]}")
                    exit()
                """
            except z3.Z3Exception as e:
                print(f"-> Z3 error while MBP: {e}")
        else:
            print(f"\n UNSAT! F-Solver couldn't find counter example.")
            print(f"Optimal Counterfactual r = {r_floats}")
            print(f"\n Start verification of r being valid for all y: ")
            verifier = z3.Solver()
            final_r_subs = [(r_vars[i], z3.RealVal(r_floats[i])) for i in range(7)]
            phi_verified = z3.substitute(original_phi[2], *final_r_subs)
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