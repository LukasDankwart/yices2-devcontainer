from z3 import *


def phi(r_val, y_var):
    return z3.Implies(y_var > 0, r_val > y_var)

def error_condition(r_val, y_var):
    return z3.Not(phi(r_val, y_var))

def gen_by_substitution(constraint, substitution):
    return z3.substitute(constraint, substitution)

def quantifier_elimination(exists_variables, formula):
    exists_error = z3.Exists(exists_variables, formula)
    qe_tactic = z3.Tactic('qe')
    bad_space_r = qe_tactic(exists_error).as_expr()
    gen_constraint = z3.Not(bad_space_r)
    return gen_constraint

def model_based_projection(r, current_r, y, counter_example):
    core_conditions = []
    error_expr = error_condition(current_r, y)

    # Add all AND conditions that are true for given counter example
    if z3.is_and(error_expr):
        for clause in error_expr.children():
            if z3.is_true(counter_example.eval(clause)):
                core_conditions.append(z3.substitute(clause, (current_r, r)))
    else:
        core_conditions.append(error_condition(r, y))

    implicant = z3.And(core_conditions)

    exists_core = z3.Exists([y], implicant)

    #mbp_tactic = z3.Tactic('qe-light')
    mbp_tactic = z3.Then(z3.Tactic('simplify'), z3.Tactic('qe'))
    projected_core = mbp_tactic(exists_core).as_expr()

    gen_constraint = z3.Not(projected_core)
    return gen_constraint


def main(mode="sub"):
    # Define variables for simple example
    r = z3.Real("r")
    y = z3.Real("y")

    # Initialize both solvers: Optimizer (E-Solver) and Std. Solver (F-Solver)
    e_solver = z3.Optimize()
    f_solver = z3.Solver()

    # Define objective
    e_solver.minimize(r)

    # Set y to <= 2
    f_solver.add(y <= 2)

    while e_solver.check() == z3.sat:
        current_model = e_solver.model()
        current_r = current_model.eval(r, model_completion=True)
        print(f"E-Solver predicts: r = {current_r}")

        f_solver.push()
        f_solver.add(error_condition(current_r, y))

        if f_solver.check() == z3.sat:
            counter_example = f_solver.model()
            y_val = counter_example.eval(y, model_completion=True)
            print(f"F-Solver found counter example: y = {y_val}")

            if mode == "sub":
                gen_constraint = gen_by_substitution(phi(r, y), (y, y_val))
            elif mode == "qe":
                bounded_error = z3.And(y <= 2, error_condition(r, y))
                gen_constraint = quantifier_elimination([y], bounded_error)
            elif mode == "mbp":
                gen_constraint = model_based_projection(r, current_r, y, counter_example)
            else:
                print(f"Unknown mode for generalization constraints: {mode}")
                break

            e_solver.add(gen_constraint)
            print(f"New generalization constraint: {gen_constraint}")
        else:
            print(f"Solution was found, no counter example found for r = {current_r}")
            break
        f_solver.pop()


if __name__ == "__main__":
    main(mode="mbp")