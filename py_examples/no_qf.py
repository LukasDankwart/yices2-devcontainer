from yices import *

def main():
    cfg = Config()
    ctx = Context(cfg)
    int_t = Types.int_type()

    x = Terms.new_uninterpreted_term(int_t, 'x')
    y = Terms.new_uninterpreted_term(int_t, 'y')

    # 2. Formel A: y > 0
    y_gt_0 = Terms.arith_gt0_atom(y)

    # 3. Formel B: y - x = 0
    y_sub_x = Terms.sub(y, x)
    sub_eq_zero = Terms.arith_eq0_atom(y_sub_x)

    # 4. Formel: y != x
    unequal = Terms.arith_neq_atom(y, x)

    final_formula = Terms.yand([y_gt_0, sub_eq_zero, unequal])

    ctx.assert_formula(final_formula)

    status = ctx.check_context()
    if status == Status.SAT:
        print(f"SAT: Formula is satisfiable.")
        model = Model.from_context(ctx, 1)

        xval = model.get_value(x)
        yval = model.get_value(y)
        print(f'x = {xval}, y = {yval}')
    else:
        print(f"UNSAT: Formula is unsatisfiable.")

    ctx.dispose()
    cfg.dispose()


if __name__ == "__main__":
    main()