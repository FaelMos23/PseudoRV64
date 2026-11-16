"""Pontos de implementação da geração de comandos e expressões."""

import load_previous
from ir import (
    Context, 
    ProgramIR, 
    FunctionIR, 
    Param, 
    Return, 
    Move, 
    LabelInstr, 
    Jump, 
    PrintInt, 
    PrintBool, 
    PrintString,
    Move,
    Jump,
    LabelInstr,
    Neg,
    Seqz,
    Snez,
    Li,
    Addi,
    Slli,
    Add,
    Sub,
    Mul,
    Div,
    Rem,
    Slt,
    Xor,
    Beq,
    Bne,
    Blt,
    Bge,
    Beqz,
    Bnez,
    Call,
)

from ast_nodes import (
    Block,
    VarDecl,
    Assignment,
    CallStmt,
    IfStmt,
    WhileStmt,
    ReturnStmt,
    PrintStmt,
    StringLiteral,
    TypeName,
    BinaryOperator,
    UnaryExpr,
)

from selector import Selector

from catalogue import rules, type_name

from patterns import REG, COND, EFFECT, IMM12, POW2

class CodeGenerator:
    """Coordene comandos ad hoc e seleção de expressões com DP."""

    def generate(self, program):
        """Traduza funções e comandos. Selecione expressões com DP."""

        p = ProgramIR(list(), dict())

        for f in program.functions:
            curr_f = FunctionIR(f.metadata["symbol"], list())
            p.functions.append(curr_f)

            self.ctx = Context(curr_f, p)

            # parâmetros
            for index, param in enumerate(f.parameters):
                dst = self.ctx.variable(param.metadata["symbol"])
                self.ctx.emit(Param(dst, index, origin=param.span))

            # corpo da função
            for stmt in f.body.statements:
                self.statement(stmt)

            # fim de função sem statement retorno
            if not curr_f.instructions or type(curr_f.instructions[-1]).__name__ != "Return":
                if f.return_type == TypeName.VOID:
                    self.ctx.emit(Return(None))

        return p

    # função extra, para expression
    def _literal_value(self, node):
        # valor de literal com sinal: IntLiteral, BoolLiteral (0/1) ou -IntLiteral
        if isinstance(node, UnaryExpr):
            return -node.operand.value
        return int(node.value)

    def _split_reg_imm(self, sub_results):
        # Addi/Slli aceitam o literal em qualquer lado: devolve (reg, imm)
        if isinstance(sub_results[0], int):
            return sub_results[1], sub_results[0]
        return sub_results[0], sub_results[1]

    def execute_action(self, action_name, node, sub_results, result_class, true_label, false_label):
        match action_name:

            # grupo: reg|label
            case "emit_identifier":
                return self.ctx.variable(node.metadata["symbol"])

            case "emit_label":
                self.ctx.emit(LabelInstr(node.label))

            case "emit_jump":
                self.ctx.emit(Jump(node.label))

            # grupo: dst, reg
            case "emit_move":
                dst = self.ctx.temp()
                reg = sub_results[0]
                self.ctx.emit(Move(dst, reg, origin=node.span))
                return dst

            case "emit_neg":
                dst = self.ctx.temp()
                reg = sub_results[0]
                self.ctx.emit(Neg(dst, reg, origin=node.span))
                return dst

            case "emit_seqz":
                dst = self.ctx.temp()
                reg = sub_results[0]
                self.ctx.emit(Seqz(dst, reg, origin=node.span))
                return dst
                
            case "emit_snez":
                dst = self.ctx.temp()
                reg = sub_results[0]
                self.ctx.emit(Snez(dst, reg, origin=node.span))
                return dst


            # grupo: dst, imm
            case "emit_literal_int":
                dst = self.ctx.temp()
                self.ctx.emit(Li(dst, self._literal_value(node), origin=node.span))
                return dst

            # grupo: literal sem instrução (IMM12 oferece o valor, POW2 oferece o expoente k)
            case "emit_pass":
                value = self._literal_value(node)
                if result_class == POW2:
                    return value.bit_length() - 1
                return value


            # grupo: dst, reg, imm
            case "emit_add_imm":
                dst = self.ctx.temp()
                lreg, imm = self._split_reg_imm(sub_results)
                self.ctx.emit(Addi(dst, lreg, imm, origin=node.span))
                return dst

            case "emit_sub_neg_imm":
                # x - c  =>  addi x, -c
                dst = self.ctx.temp()
                lreg = sub_results[0]
                self.ctx.emit(Addi(dst, lreg, -self._literal_value(node.right), origin=node.span))
                return dst

            case "emit_slli":
                dst = self.ctx.temp()
                lreg, shift = self._split_reg_imm(sub_results)
                self.ctx.emit(Slli(dst, lreg, shift, origin=node.span))
                return dst

            
            # grupo: dst, lreg, rreg
            case "emit_add":
                dst = self.ctx.temp()
                lreg = sub_results[0]
                rreg = sub_results[1]
                self.ctx.emit(Add(dst, lreg, rreg, origin=node.span))
                return dst
            
            case "emit_sub":
                dst = self.ctx.temp()
                lreg = sub_results[0]
                rreg = sub_results[1]
                self.ctx.emit(Sub(dst, lreg, rreg, origin=node.span))
                return dst
            
            case "emit_mul":
                dst = self.ctx.temp()
                lreg = sub_results[0]
                rreg = sub_results[1]
                self.ctx.emit(Mul(dst, lreg, rreg, origin=node.span))
                return dst
            
            case "emit_div":
                dst = self.ctx.temp()
                lreg = sub_results[0]
                rreg = sub_results[1]
                self.ctx.emit(Div(dst, lreg, rreg, origin=node.span))
                return dst
            
            case "emit_rem":
                dst = self.ctx.temp()
                lreg = sub_results[0]
                rreg = sub_results[1]
                self.ctx.emit(Rem(dst, lreg, rreg, origin=node.span))
                return dst
            
            case "emit_slt":
                dst = self.ctx.temp()
                lreg = sub_results[0]
                rreg = sub_results[1]
                self.ctx.emit(Slt(dst, lreg, rreg, origin=node.span))
                return dst

            case "emit_sgt":
                # x > y <=> y < x
                dst = self.ctx.temp()
                lreg = sub_results[0]
                rreg = sub_results[1]
                self.ctx.emit(Slt(dst, rreg, lreg, origin=node.span))
                return dst

            case "emit_sle":
                # x <= y <=> !(y < x)
                tmp = self.ctx.temp()
                dst = self.ctx.temp()
                lreg = sub_results[0]
                rreg = sub_results[1]
                self.ctx.emit(Slt(tmp, rreg, lreg, origin=node.span))
                self.ctx.emit(Seqz(dst, tmp, origin=node.span))
                return dst

            case "emit_sge":
                # x >= y <=> !(x < y)
                tmp = self.ctx.temp()
                dst = self.ctx.temp()
                lreg = sub_results[0]
                rreg = sub_results[1]
                self.ctx.emit(Slt(tmp, lreg, rreg, origin=node.span))
                self.ctx.emit(Seqz(dst, tmp, origin=node.span))
                return dst

            case "emit_eq" | "emit_ne":
                # x == y <=> (x ^ y) == 0
                tmp = self.ctx.temp()
                dst = self.ctx.temp()
                lreg = sub_results[0]
                rreg = sub_results[1]
                self.ctx.emit(Xor(tmp, lreg, rreg, origin=node.span))
                if action_name == "emit_eq":
                    self.ctx.emit(Seqz(dst, tmp, origin=node.span))
                else:
                    self.ctx.emit(Snez(dst, tmp, origin=node.span))
                return dst
            
            case "emit_xor":
                dst = self.ctx.temp()
                lreg = sub_results[0]
                rreg = sub_results[1]
                self.ctx.emit(Xor(dst, lreg, rreg, origin=node.span))
                return dst


            # grupo: lreg, rreg, label
            case "emit_beq":
                lreg = sub_results[0]
                rreg = sub_results[1]
                self.ctx.emit(Beq(lreg, rreg, node.label, origin=node.span))
            
            case "emit_bne":
                lreg = sub_results[0]
                rreg = sub_results[1]
                self.ctx.emit(Bne(lreg, rreg, node.label, origin=node.span))
            
            case "emit_blt":
                lreg = sub_results[0]
                rreg = sub_results[1]
                self.ctx.emit(Blt(lreg, rreg, node.label, origin=node.span))
            
            case "emit_bge":
                lreg = sub_results[0]
                rreg = sub_results[1]
                self.ctx.emit(Bge(lreg, rreg, node.label, origin=node.span))


            # grupo: reg, label
            case "emit_beqz":
                reg = sub_results[0]
                self.ctx.emit(Beqz(reg, node.label, origin=node.span))
            
            case "emit_bnez":
                reg = sub_results[0]
                self.ctx.emit(Bnez(reg, node.label, origin=node.span))


            # grupo: call
            case "emit_call":
                args = list(sub_results)
                if result_class == EFFECT:
                    dst = None
                else:
                    dst = self.ctx.temp()

                # FunctionSymbol já resolvido pela semântica
                func_symbol = node.metadata["symbol"]
                self.ctx.emit(Call(dst, func_symbol, args, origin=node.span))
                return dst

            case "emit_call_cond":
                # chamada bool como condição: call, bnez e j
                dst = self.ctx.temp()
                self.ctx.emit(Call(dst, node.metadata["symbol"], list(sub_results), origin=node.span))
                self.ctx.emit(Bnez(dst, true_label, origin=node.span))
                self.ctx.emit(Jump(false_label, origin=node.span))


            # grupo: && e || como valor (REG), materializando 0/1
            case "emit_logical_reg_and" | "emit_logical_reg_or":
                dst = self.ctx.temp()
                t_label = self.ctx.label()
                f_label = self.ctx.label()
                end_label = self.ctx.label()

                # emite a condição com destinos próprios (mantém curto-circuito)
                cond_action = "emit_cond_and" if action_name == "emit_logical_reg_and" else "emit_cond_or"
                self.execute_action(cond_action, node, sub_results, COND, t_label, f_label)

                self.ctx.emit(LabelInstr(t_label))
                self.ctx.emit(Li(dst, 1, origin=node.span))
                self.ctx.emit(Jump(end_label))
                self.ctx.emit(LabelInstr(f_label))
                self.ctx.emit(Li(dst, 0, origin=node.span))
                self.ctx.emit(LabelInstr(end_label))
                return dst


            # grupo: tratamento de condições (COND) com true_label e false_label
            # os filhos COND chegam em sub_results como funções (true_label, false_label),
            # emitidas só aqui, no caminho correto
            case ("emit_cond_branch" | "emit_cond_comparison" | "emit_cond_and" | "emit_cond_or"
                  | "emit_cond_not" | "emit_cond_literal" | "emit_cond_identifier"):
                # Tratamento para BinaryExpr de comparação ou operadores lógicos
                if type(node).__name__ == "BinaryExpr":
                    op = node.operator
                    
                    # Operadores lógicos com curto-circuito (&& e ||)
                    if op == BinaryOperator.LOGICAL_AND:
                        mid_label = self.ctx.label()
                        sub_results[0](mid_label, false_label)
                        self.ctx.emit(LabelInstr(mid_label))
                        sub_results[1](true_label, false_label)
                        return
                    elif op == BinaryOperator.LOGICAL_OR:
                        mid_label = self.ctx.label()
                        sub_results[0](true_label, mid_label)
                        self.ctx.emit(LabelInstr(mid_label))
                        sub_results[1](true_label, false_label)
                        return

                    # Comparações relacionais que utilizam os registradores avaliados nos sub_results
                    lreg = sub_results[0]
                    rreg = sub_results[1]

                    if op == BinaryOperator.LESS:  # <
                        self.ctx.emit(Blt(lreg, rreg, true_label, origin=node.span))
                        self.ctx.emit(Jump(false_label, origin=node.span))
                    elif op == BinaryOperator.LESS_EQUAL:  # <= (x <= y <=> y >= x)
                        self.ctx.emit(Bge(rreg, lreg, true_label, origin=node.span))
                        self.ctx.emit(Jump(false_label, origin=node.span))
                    elif op == BinaryOperator.GREATER:  # > (x > y <=> y < x)
                        self.ctx.emit(Blt(rreg, lreg, true_label, origin=node.span))
                        self.ctx.emit(Jump(false_label, origin=node.span))
                    elif op == BinaryOperator.GREATER_EQUAL:  # >=
                        self.ctx.emit(Bge(lreg, rreg, true_label, origin=node.span))
                        self.ctx.emit(Jump(false_label, origin=node.span))
                    elif op == BinaryOperator.EQUAL:  # ==
                        self.ctx.emit(Beq(lreg, rreg, true_label, origin=node.span))
                        self.ctx.emit(Jump(false_label, origin=node.span))
                    elif op == BinaryOperator.NOT_EQUAL:  # !=
                        self.ctx.emit(Bne(lreg, rreg, true_label, origin=node.span))
                        self.ctx.emit(Jump(false_label, origin=node.span))

                elif type(node).__name__ == "UnaryExpr":
                    # Negação lógica (!) inverte os destinos verdadeiro e falso
                    if node.operator.value == "!":
                        sub_results[0](false_label, true_label)

                elif type(node).__name__ == "BoolLiteral":
                    if node.value:
                        self.ctx.emit(Jump(true_label, origin=node.span))
                    else:
                        self.ctx.emit(Jump(false_label, origin=node.span))

                elif type(node).__name__ == "IdentifierExpr":
                    reg = self.ctx.variable(node.metadata["symbol"])
                    self.ctx.emit(Bnez(reg, true_label, origin=node.span))
                    self.ctx.emit(Jump(false_label, origin=node.span))


            case _:
                raise NotImplementedError(f"Ação não implementada no gerador: {action_name}")
            
    def expression(self, node, result_class, true_label=None, false_label=None, table=None):
        """Selecione e reconstrua uma expressão, preservando curto-circuito."""
        
        # a análise é feita uma vez na raiz; os filhos reutilizam a mesma tabela
        if table is None:
            table = Selector(rules).analyze(node)
        choice = table.lookup(node, result_class)

        if choice is None:
            span_str = f" na linha {node.span.start_line}" if hasattr(node, "span") and node.span else ""
            raise RuntimeError(f"Erro de compilação: Sem cobertura para o nó {type(node).__name__} na classe {result_class}{span_str}")

        rule = choice.rule
        
        sub_results = []
        for sub_node, sub_class in choice.subproblems:
            if sub_class == COND:
                # COND não é emitida antes: a ação decide onde e com quais destinos
                res = lambda t, f, n=sub_node: self.expression(n, COND, t, f, table)
            else:
                res = self.expression(sub_node, sub_class, table=table)
            sub_results.append(res)

        return self.execute_action(rule.action, node, sub_results, result_class, true_label, false_label)

    def statement(self, node):
        """Traduza um comando ad hoc."""

        match type(node).__name__:
            case "Block":
                for stmt in node.statements:
                    self.statement(stmt)

            case "VarDecl":
                # se houver inicialização, ex.: int x = 2;
                #                               li x, 2
                if getattr(node, "initializer", None):
                    val_reg = self.expression(node.initializer, REG)
                    dst = self.ctx.variable(node.metadata["symbol"])
                    self.ctx.emit(Move(dst, val_reg, origin=node.span))

            case "Assignment":
                # ex.: y = 3;
                #      li y, 3
                val_reg = self.expression(node.value, REG)
                dst = self.ctx.variable(node.target.metadata["symbol"])
                self.ctx.emit(Move(dst, val_reg, origin=node.span))

            case "IfStmt":
                # ex.: if(cond) {
                #          cond=true;
                #      }
                #      else {
                #          cond=false;
                #      }
                #b.. ., ., (false_label/end_label)  # b.. is opposite of cond
                #true_label:
                #    cond=true
                #(    j end_label
                # false_label:
                #     cond=false
                #)  # optional
                #end_label:
                true_label = self.ctx.label()
                false_label = self.ctx.label()

                if getattr(node, "else_block", None):
                    end_label = self.ctx.label()
                else:
                    end_label = false_label


                self.expression(node.condition, COND, true_label, false_label)

                self.ctx.emit(LabelInstr(true_label))
                self.statement(node.then_block)


                if getattr(node, "else_block", None):
                    self.ctx.emit(Jump(end_label))
                    self.ctx.emit(LabelInstr(false_label))
                    self.statement(node.else_block)
                
                if end_label != false_label or not getattr(node, "else_block", None):
                    self.ctx.emit(LabelInstr(end_label))

            case "WhileStmt":
                # ex.: while(cond) {
                #          cond=true
                #      }
                #test_label:
                #   b.. ., ., end_label     # b.. is opposite of cond
                #body_label:
                #   cond=true
                #   j test_label
                #end_label:
                test_label = self.ctx.label()
                body_label = self.ctx.label()
                end_label = self.ctx.label()

                self.ctx.emit(LabelInstr(test_label))
                self.expression(node.condition, COND, true_label=body_label, false_label=end_label)

                self.ctx.emit(LabelInstr(body_label))
                self.statement(node.body)
                self.ctx.emit(Jump(test_label))

                self.ctx.emit(LabelInstr(end_label))

            case "ReturnStmt":
                # return; ou return value;
                # (li ., value)     # se houver valor
                # ret
                if getattr(node, "value", None):
                    val_reg = self.expression(node.value, REG)
                    self.ctx.emit(Return(val_reg, origin=node.span))
                else:
                    self.ctx.emit(Return(None, origin=node.span))

            case "PrintStmt":
                # print("...", value1, ...)
                for item in node.items:
                    if type(item) == StringLiteral:
                        ref = self.ctx.string(item.value)
                        self.ctx.emit(PrintString(ref, origin=item.span))
                    else:
                        val_reg = self.expression(item, REG)

                        if type_name(item) == "bool":
                            self.ctx.emit(PrintBool(val_reg, origin=item.span))
                        else:
                            self.ctx.emit(PrintInt(val_reg, origin=item.span))
                
                # fim do print pula linha
                newline_ref = self.ctx.string("\n")
                self.ctx.emit(PrintString(newline_ref))

            case "CallStmt":
                # chamada como comando usa EFFECT (resultado descartado, dst=None), seja void ou não
                self.expression(node.call, EFFECT)

            case _:
                raise NotImplementedError(f"Comando não implementado: {type(node).__name__}")