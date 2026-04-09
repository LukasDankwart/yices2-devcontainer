from z3 import *
#from enncode.gurobiModelBuilder import GurobiModelBuilder
from gurobipy import GRB
import gurobipy as gp
from z3_examples.z3_gen_example import extract_mbp_core
from fractions import Fraction

from gurobi_utils import *


import z3


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

    # Set up paths
    onnx_path = "yices_ws/networks/concrete/classifier_medium.onnx"
    smt_file = "z3_examples/gen_examples/z3_gen_fixed.smt2"
    formulas = z3.parse_smt2_file(smt_file)

    # Enncode for importing ONNX Network
    #model_builder = GurobiModelBuilder(onnx_path)
    #model_builder.build_model()
    #gurobi_model = model_builder.get_gurobi_model()

    # Initialize solvers
    e_solver = gp.Model("e_solver")
    f_solver = z3.Solver()

    # Setup solvers
    # E-Optimizer: minimize distances | r_i - x_i | (y remains unknown)
    e_solver = gp.Model("e_solver")
    gurobi_r_vars = [e_solver.addVar(lb=-200.0, ub=200.0, name=f"r{i}") for i in range(7)]
    dist_vars = e_solver.addVars(len(gurobi_r_vars), name="d_vars")
    for (idx, (r_var, d_var)) in enumerate(zip(gurobi_r_vars, dist_vars.values())):
        #e_solver.addConstr(d_var >= r_var - concrete_input[idx])
        #e_solver.addConstr(d_var >= concrete_input[idx] - r_var)
        e_solver.addConstr(d_var >= r_var)
        e_solver.addConstr(d_var >= -r_var)
    e_solver.setObjective(dist_vars.sum(), GRB.MINIMIZE)
    e_solver.setParam("OutputFlag", 0)
    # Set FOCUS to find optimal solutions!
    e_solver.setParam("MIPFocus", 2)

    # F-Solver: find y that breaks pre-condition => post-condition
    z3_r_vars = [z3.Real(f"r{i}") for i in range(7)]
    z3_y_var = z3.Real("y")
    lb_cond_y = formulas[0]
    ub_cond_y = formulas[1]
    post_cond = formulas[2]
    f_solver.add(lb_cond_y)
    f_solver.add(ub_cond_y)


    # Var Mapping (Z3Names : GurobiVar)
    r_vars_mapping = {f"r{idx}": gurobi_r_vars[idx] for idx in range(len(gurobi_r_vars))}
    gen_constraints = []

    iteration = 1
    while True:
        # (E-Solver)
        print(f"\n === Iteration {iteration} started ===")
        print(f"Call Gurobi (E-Solver) optimization...")
        e_solver.optimize()
        if e_solver.status == GRB.OPTIMAL:
            print(f"Gurobi (E-Solver) found SAT assignment to 'r' vars")
            current_r_vals = [res_var.X for res_var in gurobi_r_vars]
            print(f"Gurobi (E-Solver) predicts: r = {current_r_vals}")
            current_distance = e_solver.ObjVal
            print(f"Gurobi (E-Solver) prediction of r has L1 distance: dist(r) = {current_distance}")
        else:
            print(f"Gurobi (E-Solver) replies UNSAT")
            break

        # (F-Solver)
        f_solver.push()
        # Substitute r vars by their assignment found by gurobi in Z3 instance (skip last r cause it is the y)
        z3_current_r = [z3.RealVal(Fraction(r).limit_denominator()) for r in current_r_vals]
        z3_r_substitution = list(zip(z3_r_vars, z3_current_r))
        z3_phi_current_r = z3.substitute(post_cond, *z3_r_substitution)
        f_solver.add(z3.Not(z3_phi_current_r))
        print("\n Call Z3 (F-Solver) for current r...")
        if f_solver.check() == z3.sat:
            f_model = f_solver.model()
            counter_y = f_model.eval(z3_y_var, model_completion=True)
            print(f"Z3 (F-Solver) found SAT assignment to y (CounterExample): y = {float(counter_y.as_fraction())}")

            error_formula = z3.And(lb_cond_y, ub_cond_y, z3.Not(post_cond))
            linear_core = extract_mbp_core(error_formula, f_model, z3_r_substitution)

            exists_error = z3.Exists([z3_y_var], linear_core)
            mbp_tactic = z3.Then(z3.Tactic('simplify'), z3.Tactic('qe'))

            try:
                bad_space_for_r = mbp_tactic(exists_error).as_expr()
                gen_constraint = z3.Not(bad_space_for_r)
                """
                test_eval = z3.simplify(z3.substitute(gen_constraint, *z3_r_substitution))
                print(f"Check if current gen-constraint excludes current r : {test_eval}")
                if z3.is_true(test_eval):
                    print("ERROR: Current r is not excluded by new gen-constraint. Indicates MBP error!")
                    exit()
                """
                add_gen_constraint_to_gurobi(gen_constraint, e_solver, r_vars_mapping)
                gen_constraints.append(gen_constraint)
                gen_constraint_validation(gen_constraints, z3_r_substitution)

            except z3.Z3Exception as e:
                print(f"Z3 (F-Solver) raised error doing MBP: {e}")

        else:
            print(f"Z3 (F-Solver) replies UNSAT")
            print(f"Last found 'r' is optimal CX: r = {current_r_vals} \n")
            print(f"\n Start verification of r being valid for all y: ")
            verifier = z3.Solver()
            final_r_subs = [(z3_r_vars[i], z3.RealVal(current_r_vals[i])) for i in range(7)]
            phi_verified = z3.substitute(post_cond, *final_r_subs)
            verifier.add(z3_y_var >= -1.0, z3_y_var <= 1.0)
            verifier.add(z3.Not(phi_verified))
            result = verifier.check()
            if result == z3.unsat:
                print(f"Correctness of r was verified!")
                if e_solver.SolCount > 0:
                    print(f"Found objective value: {e_solver.ObjVal}")
                    print(f"Theoretical best bound: {e_solver.ObjBound}")
                    print(f"MIPGap: {e_solver.MIPGap * 100:.2f}")


            else:
                print(f"Verification failed. Verifier has found a counter example for y.")
                print(f"y = {float(verifier.model().eval(z3_y_var).as_fraction())}")
            break

        print(f"Gurobi (E-Solver) constraints: {e_solver.NumConstrs} ")
        #time.sleep(2)
        f_solver.pop()
        iteration += 1


def gen_constraint_validation(gen_constraints, substitution):
    gen_search_space = z3.And(*gen_constraints)
    test_eval = z3.simplify(z3.substitute(gen_search_space, *substitution))
    if z3.is_true(test_eval):
        print(f"Current r is NOT excluded from generalized search space.")
        exit()
    else:
        print(f"Current r is excluded from generalized search space.")


if __name__ == '__main__':
    main()