import subprocess

def run_yices_on_smt(smt_path):
    try:
        results = subprocess.run(
            ['yices-smt2', smt_path],
            text=True,
            capture_output=True
        )
        return results
    except FileNotFoundError:
        print(f"{smt_path} not found or not valid.")

def clean_name(name):
    if not name:
        return "unknown"
    return "v_" + name.replace(":", "_").replace(".", "_").replace("/", "_")

def format_smt_number(val):
    if val < 0:
        return f"(- {abs(val):.6f})"
    return f"{val:.6f}"