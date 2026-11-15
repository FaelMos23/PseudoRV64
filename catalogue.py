"""Ponto de implementação das regras declarativas do enunciado."""

from patterns import Rule, Pattern, Need, Args, REG, COND, IMM12, POW2, EFFECT
from patterns import signed_literal, imm12, pow2, neg_imm12
from ast_nodes import (
    BinaryExpr,
    UnaryExpr,
    IntLiteral,
    BoolLiteral,
    IdentifierExpr,
    CallExpr,
    BinaryOperator,
    UnaryOperator,
)


# predicados auxiliares
def type_name(node):
    # nome do tipo anotado pela semântica ("int", "bool" ou "void")
    t = node.metadata.get("type")
    return str(getattr(t, "value", t)).lower()

def is_bool(node):
    return type_name(node) == "bool"

def is_value(node):
    # chamada void não oferece REG
    return type_name(node) != "void"

def signed_imm12(node):
    # literal com sinal (5 ou -5) que cabe no imediato de Addi
    return signed_literal(node) and imm12(node)

def signed_neg_imm12(node):
    # literal com sinal cujo oposto cabe no imediato de Addi
    return signed_literal(node) and neg_imm12(node)


rules = [
    # literais e identificadores básicos
    Rule(
        name="literal_int_reg",
        result=REG,
        pattern=Pattern(predicate=signed_literal),
        cost=1,
        action="emit_literal_int",
    ),
    Rule(
        name="literal_bool_reg",
        result=REG,
        pattern=Pattern(kind=BoolLiteral),
        cost=1,
        action="emit_literal_int",
    ),
    Rule(
        name="identifier_reg",
        result=REG,
        pattern=Pattern(kind=IdentifierExpr),
        cost=0,
        action="emit_identifier",
    ),
    
    # literais sem custo
    Rule(
        name="literal_imm12",
        result=IMM12,
        pattern=Pattern(predicate=signed_imm12),
        cost=0,
        action="emit_pass",
    ),
    Rule(
        name="literal_pow2",
        result=POW2,
        pattern=Pattern(kind=IntLiteral, predicate=pow2),
        cost=0,
        action="emit_pass",
    ),

    # neg
    Rule(
        name="neg_reg",
        result=REG,
        pattern=Pattern(kind=UnaryExpr, operator=UnaryOperator.NEGATE, children=(Need(REG),)),
        cost=1,
        action="emit_neg",
    ),

    # reg, reg, reg
    Rule(
        name="add_reg",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.ADD, children=(Need(REG), Need(REG))),
        cost=1,
        action="emit_add",
    ),
    Rule(
        name="sub_reg",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.SUBTRACT, children=(Need(REG), Need(REG))),
        cost=1,
        action="emit_sub",
    ),
    Rule(
        name="mul_reg",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.MULTIPLY, children=(Need(REG), Need(REG))),
        cost=1,
        action="emit_mul",
    ),
    Rule(
        name="div_reg",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.DIVIDE, children=(Need(REG), Need(REG))),
        cost=1,
        action="emit_div",
    ),
    Rule(
        name="rem_reg",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.REMAINDER, children=(Need(REG), Need(REG))),
        cost=1,
        action="emit_rem",
    ),

    # otimizações com imm e pow2 (Addi e Slli)
    Rule(
        name="add_imm_right",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.ADD, children=(Need(REG), Need(IMM12))),
        cost=1,
        action="emit_add_imm",
    ),
    Rule(
        name="add_imm_left",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.ADD, children=(Need(IMM12), Need(REG))),
        cost=1,
        action="emit_add_imm",
    ),
    Rule(
        name="sub_neg_imm",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.SUBTRACT, children=(Need(REG), Pattern(predicate=signed_neg_imm12))),
        cost=1,
        action="emit_sub_neg_imm",
    ),
    Rule(
        name="mul_pow2_right",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.MULTIPLY, children=(Need(REG), Need(POW2))),
        cost=1,
        action="emit_slli",
    ),
    Rule(
        name="mul_pow2_left",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.MULTIPLY, children=(Need(POW2), Need(REG))),
        cost=1,
        action="emit_slli",
    ),

    # comparações
    Rule(
        name="slt_reg",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.LESS, children=(Need(REG), Need(REG))),
        cost=1,
        action="emit_slt",
    ),
    Rule(
        name="sgt_reg",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.GREATER, children=(Need(REG), Need(REG))),
        cost=1,
        action="emit_sgt",
    ),
    Rule(
        name="sle_reg",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.LESS_EQUAL, children=(Need(REG), Need(REG))),
        cost=2,
        action="emit_sle",
    ),
    Rule(
        name="sge_reg",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.GREATER_EQUAL, children=(Need(REG), Need(REG))),
        cost=2,
        action="emit_sge",
    ),
    Rule(
        name="eq_reg",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.EQUAL, children=(Need(REG), Need(REG))),
        cost=2,
        action="emit_eq",
    ),
    Rule(
        name="ne_reg",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.NOT_EQUAL, children=(Need(REG), Need(REG))),
        cost=2,
        action="emit_ne",
    ),

    # comparações para COND (Controle de Fluxo Direto)
    # uma regra por operador relacional (operator=None aceitaria +, && etc.)
    *[
        Rule(
            name=f"cond_relop_{op.name.lower()}",
            result=COND,
            pattern=Pattern(kind=BinaryExpr, operator=op, children=(Need(REG), Need(REG))),
            cost=2,
            action="emit_cond_comparison",
        )
        for op in (
            BinaryOperator.LESS,
            BinaryOperator.LESS_EQUAL,
            BinaryOperator.GREATER,
            BinaryOperator.GREATER_EQUAL,
            BinaryOperator.EQUAL,
            BinaryOperator.NOT_EQUAL,
        )
    ],
    Rule(
        name="cond_bool_literal",
        result=COND,
        pattern=Pattern(kind=BoolLiteral),
        cost=1,
        action="emit_cond_literal",
    ),
    Rule(
        name="cond_identifier",
        result=COND,
        pattern=Pattern(kind=IdentifierExpr, predicate=is_bool),
        cost=2,
        action="emit_cond_identifier",
    ),

    # and, or, not
    Rule(
        name="not_reg",
        result=REG,
        pattern=Pattern(kind=UnaryExpr, operator=UnaryOperator.NOT, children=(Need(REG),)),
        cost=1,
        action="emit_seqz",
    ),
    Rule(
        name="not_cond",
        result=COND,
        pattern=Pattern(kind=UnaryExpr, operator=UnaryOperator.NOT, children=(Need(COND),)),
        cost=0,
        action="emit_cond_not",
    ),
    Rule(
        name="logical_and_cond",
        result=COND,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.LOGICAL_AND, children=(Need(COND), Need(COND))),
        cost=0,
        action="emit_cond_and",
    ),
    Rule(
        name="logical_or_cond",
        result=COND,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.LOGICAL_OR, children=(Need(COND), Need(COND))),
        cost=0,
        action="emit_cond_or",
    ),
    Rule(
        name="logical_and_reg",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.LOGICAL_AND, children=(Need(COND), Need(COND))),
        cost=3,
        action="emit_logical_reg_and",
    ),
    Rule(
        name="logical_or_reg",
        result=REG,
        pattern=Pattern(kind=BinaryExpr, operator=BinaryOperator.LOGICAL_OR, children=(Need(COND), Need(COND))),
        cost=3,
        action="emit_logical_reg_or",
    ),

    # call
    Rule(
        name="call_expr",
        result=REG,
        pattern=Pattern(kind=CallExpr, children=(Args(REG),), predicate=is_value),
        cost=1,
        action="emit_call",
    ),
    Rule(
        name="call_effect",
        result=EFFECT,
        pattern=Pattern(kind=CallExpr, children=(Args(REG),)),
        cost=1,
        action="emit_call",
    ),
    Rule(
        name="call_cond",
        result=COND,
        pattern=Pattern(kind=CallExpr, children=(Args(REG),), predicate=is_bool),
        cost=3,
        action="emit_call_cond",
    ),
]

def catalogue():
    """Codifique o catálogo do enunciado com Rule e Pattern."""

    return rules