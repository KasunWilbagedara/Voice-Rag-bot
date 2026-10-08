"""
Safe Mathematical Calculator Tool.

Evaluates mathematical, statistical, or financial calculations safely using Python AST
without LLM hallucination or code injection risks.
"""

import ast
import operator
from typing import Dict, Any

from backend_with_tools.tools.base import register_tool


@register_tool(
    name="calculate_expression",
    description="Evaluates mathematical, statistical, or financial calculations safely without LLM arithmetic errors (e.g. '45000 * 0.15', '(120 + 45) / 2').",
)
def calculate_expression(expression: str) -> Dict[str, Any]:
    """Safely evaluates a math expression using Python AST."""
    allowed_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv,
    }

    def _eval(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Constants must be numeric")
        elif isinstance(node, ast.BinOp):
            op = type(node.op)
            if op not in allowed_operators:
                raise ValueError(f"Operator {op.__name__} not permitted.")
            return allowed_operators[op](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            op = type(node.op)
            if op not in allowed_operators:
                raise ValueError(f"Unary operator {op.__name__} not permitted.")
            return allowed_operators[op](_eval(node.operand))
        raise ValueError(f"Unsupported AST node: {type(node).__name__}")

    try:
        clean_expr = expression.replace(",", "").strip()
        tree = ast.parse(clean_expr, mode="eval")
        result = _eval(tree.body)
        return {
            "expression": expression,
            "result": round(result, 4) if isinstance(result, float) else result,
            "status": "success",
        }
    except Exception as e:
        return {"expression": expression, "error": str(e), "status": "failed"}
