"""Purchase-order calculations. Pure functions: no network access or Streamlit dependency."""
from __future__ import annotations
import ast
from collections import defaultdict
from dataclasses import dataclass
from math import ceil, isfinite
import re

MEALS = ("Breakfast", "Lunch", "Dinner")


def number(value, default=0.0):
    try:
        if value is None or str(value).strip() == "":
            return default
        n = float(str(value).replace(",", ""))
        return n if isfinite(n) else default
    except (ValueError, TypeError):
        return default


def identifier(value):
    s = str(value).strip()
    try:
        return str(int(float(s)))
    except (ValueError, TypeError):
        return s


def table_to_records(grid):
    if not grid:
        return []
    headers = [str(c).strip() for c in grid[0]]
    return [dict(zip(headers, row + [""] * max(0, len(headers) - len(row))))
            for row in grid[1:]
            if row and any(c is not None and str(c).strip() for c in row)]


def ingredient_index(records):
    result = {}
    for record in records:
        idx = identifier(record.get("id", ""))
        if idx and record.get("item"):
            result[idx] = record
    return result


def parse_recipe_matrix(grid, ingredients):
    """V3 Recipe: A=category, B=drink name, C onward ingredient IDs from row 1.
    Maintains a legacy fallback for the older single-name/section-row layout.
    """
    if len(grid)<3:return [],[]
    header=[str(x).strip().lower() for x in grid[0][:2]]
    v3=header==['category','id no:'] or (header and header[0]=='category')
    offset=2 if v3 else 1
    ids=[identifier(v) for v in grid[0]]
    names=grid[1];drinks=[];issues=[];current_category='Uncategorised'
    for rindex,row in enumerate(grid[2:],start=3):
        if not row:continue
        if v3:
            category=str(row[0]).strip() or 'Uncategorised'
            name=str(row[1]).strip() if len(row)>1 else ''
        else:
            name=str(row[0]).strip();category=current_category
        if not name:continue
        vals=[(col,number(v)) for col,v in enumerate(row[offset:],start=offset)
              if v not in (None,'') and number(v)!=0]
        if not vals:
            if not v3:current_category=name
            continue
        members=[]
        for col,qty in vals:
            iid=ids[col] if col<len(ids) else ''
            master=ingredients.get(iid)
            if master is None:
                issues.append(f'{name}: unmatched ingredient ID {iid} in column {col+1}')
                continue
            members.append({'ingredient_id':iid,'name':str(master.get('item',names[col] if col<len(names) else iid)),
                            'qty':qty,'unit':str(master.get('unit','')),'category':str(master.get('category','')),
                            'row':rindex,'col':col+1})
        drinks.append({'name':name,'category':category,'row':rindex,'ingredients':members})
    return drinks,issues


class UnsafeFormula(ValueError):
    pass


def evaluate_formula(formula, variables):
    """Arithmetic evaluator: never Python eval; only + - * /, parentheses, max/min/ceil."""
    permitted_functions = {"max": max, "min": min, "ceil": ceil, "round": round}
    permitted_ops = {ast.Add: lambda a, b: a+b, ast.Sub: lambda a,b: a-b,
                     ast.Mult: lambda a,b: a*b, ast.Div: lambda a,b: a/b}
    def read(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id in variables:
            return float(variables[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in permitted_ops:
            return permitted_ops[type(node.op)](read(node.left), read(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return read(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in permitted_functions and not node.keywords:
            return permitted_functions[node.func.id](*[read(x) for x in node.args])
        raise UnsafeFormula("Only numeric variables GST, TBL, PACK, BOTTLE, YIELD, B_GST, L_GST and arithmetic/max/min/ceil/round are supported")
    try:
        result = read(ast.parse(str(formula), mode="eval").body)
        if not isfinite(result):
            raise UnsafeFormula("Formula produced a non-finite value")
        return max(0., result)
    except (ZeroDivisionError, SyntaxError, OverflowError, ValueError, TypeError) as exc:
        raise UnsafeFormula(str(exc)) from exc


def interpolate_cases(row, guests):
    """Interpolate the guest columns supplied by PO_Alcohol_Matrix.

    Band anchors (not just their quantities) come from sheet column headings.
    """
    guests=max(0.,number(guests))
    points=sorted((int(str(k)),number(v)) for k,v in row.items()
                  if str(k).strip().isdigit() and int(str(k))>0)
    if not points or guests<=0:return 0.
    if guests<points[0][0]:return points[0][1]*guests/points[0][0]
    if guests>=points[-1][0]:return points[-1][1]*guests/points[-1][0]
    for (x1,y1),(x2,y2) in zip(points,points[1:]):
        if x1<=guests<=x2:return y1+(guests-x1)*(y2-y1)/(x2-x1)
    return 0.

def verify_recipe_ids(recipes, ingredients):
    return sorted({it["ingredient_id"] for rec in recipes for it in rec["ingredients"] if it["ingredient_id"] not in ingredients})
