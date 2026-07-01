"""Safe arithmetic evaluator (no eval()) used as a lightweight tool."""
import ast
import operator as op

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Evaluate a precise arithmetic expression, e.g. '(1200 * 0.085) / 12'.",
        "parameters": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    },
}

_OPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
    ast.Pow: op.pow, ast.USub: op.neg, ast.Mod: op.mod, ast.FloorDiv: op.floordiv,
}


def _eval(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("Unsupported expression")


def run(expression: str) -> dict:
    try:
        tree = ast.parse(expression, mode="eval")
        return {"result": _eval(tree.body), "ok": True}
    except Exception as e:
        return {"result": None, "ok": False, "error": str(e)}
