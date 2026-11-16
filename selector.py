"""Ponto de implementação do reconhecimento de padrões e custos mínimos."""

from patterns import *

class Choice:
    # guarda a regra de menor custo e os subproblemas necessários para a reconstrução

    def __init__(self, cost, rule, subproblems):
        self.cost = cost
        self.rule = rule
        self.subproblems = subproblems  # tupla de pares (sub_no, sub_classe)

class SelectionTable:
    # tabela que armazena os custos mínimos e escolhas por nó e classe de resultado

    def __init__(self):
        self._table = {}

    def put(self, node, result_class, choice):
        # chave por identidade do nó (id); o nó fica guardado para o id não ser reutilizado
        self._table[(id(node), result_class)] = (node, choice)

    def lookup(self, node, result_class):
        # retorna o Choice correspondente ou None se não houver cobertura
        entry = self._table.get((id(node), result_class), None)
        return entry[1] if entry is not None else None

class Selector:
    """Selecione coberturas sem executar expressões ou emitir instruções."""

    def __init__(self, rules):
        self.rules = tuple(rules)

    def analyze(self, expr):
        """Calcule mínimos por nó/classe sem emitir instruções."""

        table = SelectionTable()
        
        # função interna recursiva para percorrer a árvore em pós-ordem (filhos primeiro)
        def compute(node):
            if node is None:
                return

            # 1) visita filhos antes (pós-ordem)
            for child in self._get_children(node):
                compute(child)

            # 2) verifica por regra
            for rule in self.rules:
                # o casamento já associa cada ponto 'Need' (ou argumento de 'Args') ao seu nó, na ordem do padrão
                subproblems = []
                if self._match_pattern(rule.pattern, node, subproblems):
                    # tenta resolver os subproblemas exigidos pelos pontos 'Need'
                    total_cost = rule.cost
                    possible = True

                    for child_node, result_class in subproblems:
                        # consulta o custo ótimo do filho para a classe exigida
                        child_choice = table.lookup(child_node, result_class)
                        if child_choice is None:
                            possible = False
                            break
                        
                        total_cost += child_choice.cost

                    # se a cobertura for possível, verifica se é a mais barata para esta classe
                    if possible:
                        existing_choice = table.lookup(node, rule.result)
                        if existing_choice is None or total_cost < existing_choice.cost:
                            new_choice = Choice(total_cost, rule, tuple(subproblems))
                            table.put(node, rule.result, new_choice)

        compute(expr)
        return table

    def _get_children(self, node):
        # retorna os filhos relevantes do nó da AST para o percurso
        # os filhos podem estar em campos específicos, left/right, operando, arguments, ...

        children = []
        for attr in ["left", "right", "operand", "arguments", "condition", "then_block", "else_block", "body"]:
            val = getattr(node, attr, None)
            if val is not None:
                if isinstance(val, list):
                    children.extend(val)
                else:
                    children.append(val)
        return children

    def _match_pattern(self, pattern: Pattern, node, subproblems) -> bool:
        # verifica padrão estrutural, tipo, operador e predicados
        # acumula em subproblems os pares (sub_no, sub_classe) na ordem dos pontos Need

        if pattern is None:
            return True
        
        if pattern.kind is not None and not isinstance(node, pattern.kind):
            return False
        
        if pattern.operator is not None:
            node_op = getattr(node, "operator", None)
            if node_op != pattern.operator:
                return False
                
        if pattern.predicate is not None:
            if not pattern.predicate(node):
                return False

            # predicado sem filhos reconhece a subárvore inteira
            if not pattern.children:
                return True

        # Args(classe) como único filho: exige a classe em cada argumento (inclusive lista vazia)
        if len(pattern.children) == 1 and isinstance(pattern.children[0], Args):
            arguments = getattr(node, "arguments", None)
            if arguments is None:
                return False
            for arg in arguments:
                subproblems.append((arg, pattern.children[0].result_class))
            return True

        # nos demais casos a quantidade de filhos deve coincidir
        children = self._get_children(node)
        if len(children) != len(pattern.children):
            return False

        for sub_pattern, child in zip(pattern.children, children):
            if isinstance(sub_pattern, Need):
                subproblems.append((child, sub_pattern.result_class))
            elif isinstance(sub_pattern, Pattern):
                # padrão aninhado: o filho precisa casar estruturalmente
                if not self._match_pattern(sub_pattern, child, subproblems):
                    return False

        return True