import numpy as np
from z3 import *
#from enncode.gurobiModelBuilder import GurobiModelBuilder
from gurobipy import GRB
import gurobipy as gp
from z3_examples.z3_gen_example import extract_mbp_core
from queue import Queue
from collections import deque

import z3

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

def main():
    onnx_path = "yices_ws/networks/concrete/classifier_medium.onnx"
    smt_file = "z3_examples/gen_examples/z3_gen_fixed.smt2"

    # Setup gurobi instance
    model_builder = GurobiModelBuilder(onnx_path)
    model_builder.build_model()
    gurobi_model = model_builder.get_gurobi_model()
    e_solver = gurobi_model
    # Define gurobi Vars and objective for optimization
    gurobi_input_vars = model_builder.get_input_vars()
    gurobi_output_vars = model_builder.get_output_vars()
    dist_vars = gurobi_model.addVars(len(gurobi_input_vars) - 1, name="dist_vars")
    gurobi_res_vars = [e_solver.addVar(name=f"r{i}") for i in range(len(gurobi_input_vars) - 1)]
    for (idx, (name, var)) in enumerate(gurobi_input_vars.items()):
        # Every input var 0...6 is fixed to concrete input; input var 7 represents missing input between -1 and 1
        if idx == 7:
            e_solver.addConstr(var >= -1.0, f"{name}_lb")
            e_solver.addConstr(1.0 >= var, f"{name}_lb")
            continue
        dist_var = dist_vars[idx]
        res_var = gurobi_res_vars[idx]
        e_solver.addConstr(var == concrete_input[idx] + res_var, f"{name}_concrete_input")
        #e_solver.addConstr(concrete_input[idx] >= var, f"{name}_ub")

        # Encode dist_L1 = | res_var - input_val |
        e_solver.addConstr(dist_var >= res_var - concrete_input[idx])
        e_solver.addConstr(dist_var >= concrete_input[idx] - res_var)


    # Define post condition: output1 >= output0
    target_class = 1
    target_idx = list(gurobi_output_vars.keys())[target_class]
    for flat_idx, (_, output_var) in enumerate(gurobi_output_vars.items()):
        if target_class != flat_idx:
            c_dist = gurobi_model.addConstr(gurobi_output_vars[target_idx] >= output_var + 0.001)
    e_solver.setObjective(dist_vars.sum(), GRB.MINIMIZE)
    e_solver.setParam("OutputFlag", 0)
    # Set FOCUS to find optimal solutions!
    e_solver.setParam("MIPFocus", 2)

    # Setup Z3 solver and formulas
    z3_formulas = z3.parse_smt2_file(smt_file)
    z3_original_phi = z3_formulas
    z3_r_vars = [z3.Real(f'r{i}') for i in range(7)]
    z3_y = z3.Real('y')
    f_solver = z3.Solver()
    f_solver.add(z3_original_phi[0])
    f_solver.add(z3_original_phi[1])

    # Var Mapping (Z3Names : GurobiVar)
    r_vars_mapping = {f"r{idx}": gurobi_res_vars[idx] for idx in range(len(gurobi_res_vars))}

    # DEBUGGING PURPOSE
    last_dist = 0
    last_dist_vals = deque()

    # Starting EF loop
    iteration = 1
    while True:
        # (E-Solver)
        print(f"\n === Iteration {iteration} started ===")
        # First we let E-Solver search for optimal assignment to 'r'
        print(f"Call Gurobi (E-Solver) optimization...")
        e_solver.optimize()
        if e_solver.status == GRB.OPTIMAL:
            print(f"Gurobi (E-Solver) found SAT assignment to 'r' vars")
            current_r_vals = [res_var.X for res_var in gurobi_res_vars]
            print(f"Gurobi (E-Solver) predicts: r = {current_r_vals}")
            current_distance = sum([abs(x) for x in current_r_vals[:7]])
            print(f"Gurobi (E-Solver) prediction of r has L1 distance: dist(r) = {current_distance}")
            last_dist_vals.append(current_distance)
        else:
            print(f"Gurobi (E-Solver) replies UNSAT")
            break

        # (F-Solver)
        f_solver.push()
        # Substitute r vars by their assignment found by gurobi in Z3 instance (skip last r cause it is the y)
        z3_current_r = [z3.RealVal(r) for r in current_r_vals[:7]]
        z3_r_substitution = list(zip(z3_r_vars, z3_current_r))
        z3_phi_current_r = z3.substitute(z3_original_phi[2], *z3_r_substitution)
        f_solver.add(z3.Not(z3_phi_current_r))

        print("\n Call Z3 (F-Solver) for current r...")
        if f_solver.check() == z3.sat:
            f_model = f_solver.model()
            counter_y = f_model.eval(z3_y, model_completion=True)
            print(f"Z3 (F-Solver) found SAT assignment to y (CounterExample): y = {float(counter_y.as_fraction())}")

            error_formula = z3.Not(z3_original_phi[2])
            linear_core = extract_mbp_core(error_formula, f_model, z3_r_substitution)

            exists_error = z3.Exists([z3_y], linear_core)
            mbp_tactic = z3.Then(z3.Tactic('simplify'), z3.Tactic('qe'))

            try:
                bad_space_for_r = mbp_tactic(exists_error).as_expr()
                gen_constraint = z3.Not(bad_space_for_r)
                add_gen_constraint_to_gurobi(gen_constraint, e_solver, r_vars_mapping)

            except z3.Z3Exception as e:
                print(f"Z3 (F-Solver) raised error doing MBP: {e}")


            """
            # DEBUGGING PURPOSE
            if last_dist - current_distance > 0.02 :
                print(f"PROBLEM: Distance dropped from {last_dist} to {current_distance}")
                exit()
            last_dist = current_distance

            # Check for convergence of the distance in last n iterations
            print(f"Check convergence...")
            last_n_distances = list(last_dist_vals)
            dist_differences = np.array([abs(dist - current_distance) for dist in last_n_distances])
            if np.max(dist_differences) < 0.02 and len(last_n_distances) >= 20:
                print(f"Convergence assumed, check for counter example y: ")
                verifier = z3.Solver()
                final_r_subs = [(z3_r_vars[i], z3.RealVal(current_r_vals[i])) for i in range(7)]
                phi_verified = z3.substitute(z3_original_phi, *final_r_subs)
                verifier.add(z3_y >= -1.0, z3_y <= 1.0)
                verifier.add(z3.Not(phi_verified))
                result = verifier.check()
                if result == z3.unsat:
                    print(f"Correctness of r was verified!")
                else:
                    print(f"Verification failed. Verifier has found a counter example for y.")
                    print(f"y = {float(verifier.model().eval(z3_y).as_fraction())}")
            elif len(last_n_distances) >= 20:
                last_dist_vals.popleft()
            """

        else:
            print(f"Z3 (F-Solver) replies UNSAT")
            print(f"Last found 'r' is optimal CX: r = {current_r_vals} \n")
            print(f"\n Start verification of r being valid for all y: ")
            verifier = z3.Solver()
            final_r_subs = [(z3_r_vars[i], z3.RealVal(current_r_vals[i])) for i in range(7)]
            phi_verified = z3.substitute(z3_original_phi[2], *final_r_subs)
            verifier.add(z3_y >= -1.0, z3_y <= 1.0)
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
                print(f"y = {float(verifier.model().eval(z3_y).as_fraction())}")
            break

        print(f"Gurobi (E-Solver) constraints: {e_solver.NumConstrs} ")
        #time.sleep(2)
        f_solver.pop()
        iteration += 1

def check_optimum(dist_threshold):
    #TODO: Basically nonsense, gurobi cant manually show optimality for given r over all y in (lb,ub)
    onnx_path = "yices_ws/networks/concrete/classifier_medium.onnx"
    model_builder = GurobiModelBuilder(onnx_path)
    model_builder.build_model()
    gurobi_model = model_builder.get_gurobi_model()
    e_solver = gurobi_model
    # Define gurobi Vars and objective for optimization
    gurobi_input_vars = model_builder.get_input_vars()
    gurobi_output_vars = model_builder.get_output_vars()
    dist_vars = gurobi_model.addVars(len(gurobi_input_vars) - 1, name="dist_vars")
    gurobi_res_vars = [e_solver.addVar(name=f"r{i}") for i in range(len(gurobi_input_vars) - 1)]
    for (idx, (name, var)) in enumerate(gurobi_input_vars.items()):
        # Every input var 0...6 is fixed to concrete input; input var 7 represents missing input between -1 and 1
        if idx == 7:
            e_solver.addConstr(var >= -1.0, f"{name}_lb")
            e_solver.addConstr(1.0 >= var, f"{name}_lb")
            continue
        dist_var = dist_vars[idx]
        res_var = gurobi_res_vars[idx]
        e_solver.addConstr(var == concrete_input[idx] + res_var, f"{name}_concrete_input")
        # e_solver.addConstr(concrete_input[idx] >= var, f"{name}_ub")

        # Encode dist_L1 = | res_var - input_val |
        e_solver.addConstr(dist_var >= res_var - concrete_input[idx])
        e_solver.addConstr(dist_var >= concrete_input[idx] - res_var)

    # Define post condition: output1 >= output0
    target_class = 1
    target_idx = list(gurobi_output_vars.keys())[target_class]
    for flat_idx, (_, output_var) in enumerate(gurobi_output_vars.items()):
        if target_class != flat_idx:
            c_dist = gurobi_model.addConstr(gurobi_output_vars[target_idx] >= output_var + 0.001)

    # Final check if model exists, with distance smaller given threshold
    l1_distance_expr = gp.quicksum(dist_vars)
    e_solver.addConstr(l1_distance_expr <= dist_threshold)
    e_solver.setObjective(dist_vars.sum(), GRB.MINIMIZE)
    e_solver.setParam("MIPFocus", 1)
    e_solver.Params.SolutionLimit = 1
    e_solver.optimize()
    if e_solver.Status == GRB.OPTIMAL:
        print(f"UNSAT: Gurobi couldn't find a model for with less distance then {dist_threshold}.")
    elif e_solver.Status == GRB.OPTIMAL or e_solver.Status == GRB.SOLUTION_LIMIT:
        print(f"SAT: Previous found model for CX is not optimal!")
        better_r_vals = [v.X for v in gurobi_input_vars.values()]
        print(better_r_vals)
    else:
        print(f"Gurobi canceled with status: {e_solver.Status}")


def add_gen_constraint_to_gurobi(gen_constraint, gurobi_model, gurobi_vars, eps=1e-5):
    z3_expr = gen_constraint
    # Transformation into Negation Normalform
    goal = z3.Goal()
    goal.add(z3_expr)
    nnf_expr = z3.Tactic('nnf')(goal)[0][0]
    # Enforce gurobi encoding of the Z3 expression
    enforce(nnf_expr, gurobi_model, gurobi_vars)
    gurobi_model.update()
    print("Z3 Gen-Constraint successfully translated to Gurobi (E-Solver)")


def parse_arith(node, gurobi_vars):
    """ Translates every arithmetic Z3-node into Gurobi linear expression """

    # Check subexpression being a number
    if z3.is_rational_value(node):
        return float(node.numerator_as_long()) / float(node.denominator_as_long())
    elif z3.is_int_value(node):
        return int(node.as_long())
    elif z3.is_algebraic_value(node):
        # Nur für den Notfall, falls MBP irrationale Wurzeln erzeugt
        return float(node.approx(20).as_fraction())

    # Check if node is variable
    elif z3.is_const(node):
        name = str(node.decl().name())
        if name in gurobi_vars:
            return gurobi_vars[name]
        else:
            raise KeyError(f"Unknown variable '{name}' found, missing in var. mapping.")

    # Translate each operation case
    elif z3.is_add(node):
        # Sum over all children (summands)
        return gp.quicksum(parse_arith(c, gurobi_vars) for c in node.children())
    elif z3.is_mul(node):
        res = 1.0
        # Product of all children
        for c in node.children():
            res *= parse_arith(c, gurobi_vars)
        return res
    elif z3.is_sub(node):
        children = node.children()
        res = parse_arith(children[0], gurobi_vars)
        # Subtract each child
        for c in children[1:]:
            res -= parse_arith(c, gurobi_vars)
        return res

    else:
        raise ValueError(f"Unknown math-type of node: {node} (Z3-Declaration: {node.decl()})")


def get_gurobi_ineq(is_not, ineq_node, gurobi_vars, eps=1e-5):
    """ Translates strict inequalities to Gurobi-inequalities with epsilon deviation """
    lhs = parse_arith(ineq_node.children()[0], gurobi_vars)
    rhs = parse_arith(ineq_node.children()[1], gurobi_vars)

    # Fetch operator of expression
    is_le = z3.is_le(ineq_node)
    is_ge = z3.is_ge(ineq_node)
    is_lt = z3.is_lt(ineq_node)
    is_gt = z3.is_gt(ineq_node)
    is_eq = z3.is_eq(ineq_node)

    if is_not:  # If negated, switch the operator accordingly
        if is_le:
            is_gt = True; is_le = False
        elif is_ge:
            is_lt = True; is_ge = False
        elif is_lt:
            is_ge = True; is_lt = False
        elif is_gt:
            is_le = True; is_gt = False
        elif is_eq:
            raise NotImplementedError("Expression 'Not(==)' needs to binary variables")

    if is_le:
        return lhs <= rhs
    elif is_ge:
        return lhs >= rhs
    elif is_lt:
        return lhs <= rhs - eps
    elif is_gt:
        return lhs >= rhs + eps
    elif is_eq:
        return lhs == rhs


def enforce(node, gurobi_model, gurobi_vars):
    """ Traverse through the AST and piecewise encode each subformula as Gurobi constraint"""
    if z3.is_and(node):
        for child in node.children():
            enforce(child, gurobi_model, gurobi_vars)

    elif z3.is_or(node):
        # If node is a disjunction, create binary vars. for each subformula
        bin_vars = []
        for child in node.children():
            b = gurobi_model.addVar(vtype=GRB.BINARY)
            bin_vars.append(b)

            # Check if child is negated
            is_not = z3.is_not(child)
            ineq_node = child.children()[0] if is_not else child

            # Inequality holds
            gurobi_ineq = get_gurobi_ineq(is_not, ineq_node, gurobi_vars)
            gurobi_model.addGenConstrIndicator(b, True, gurobi_ineq)

        # At least one binary var has to be true (1)
        gurobi_model.addConstr(gp.quicksum(bin_vars) >= 1)

    else:
        # Single unequality (leaf) of the tree
        is_not = z3.is_not(node)
        ineq_node = node.children()[0] if is_not else node
        gurobi_ineq = get_gurobi_ineq(is_not, ineq_node, gurobi_vars)
        gurobi_model.addConstr(gurobi_ineq)


if __name__ == '__main__':
    main()