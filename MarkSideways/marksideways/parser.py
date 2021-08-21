from .exceptions import ParserException
from .nodes import *
from .util import *

def parse_code(tokens):
  executables = []
  while tokens.has_more():
    ex = parse_executable(tokens, True, True)
    executables.append(ex)
  return executables

_ASSIGN_OPS = {}
for ao in [
    '=',
    '+=', '-=', '*=', '/=', '%=',
    '&=', '|=', '^=',
  ]:
  _ASSIGN_OPS[ao] = True

def parse_executable(tokens, allow_complex = True, include_semicolon = True):
  next = tokens.peek()

  if next.line == 96:
    print(next)

  if next.token_type == 'KEYWORD':
    next_value = next.value
    
    if not allow_complex:
      raise ParserException(next, "Unexpected token: '" + next_value + "'")

    if next_value == 'if': return parse_if_statement(tokens)
    if next_value == 'while': return parse_while_loop(tokens)
    if next_value == 'for': return parse_for_loop(tokens)
    if next_value == 'do': return parse_do_while_loop(tokens)
    if next_value == 'return': return parse_return_statement(tokens)
    if next_value == 'break': return parse_break_statement(tokens)
    if next_value == 'continue': return parse_continue_statement(tokens)
  
  expr = parse_expression(tokens)
  if _ASSIGN_OPS.get(tokens.peek_value()) != None:
    op = tokens.pop()
    assigned_expression = parse_expression(tokens)
    output = AssignStatement(expr, op, assigned_expression)
  else:
    if isinstance(expr, FunctionInvocation):
      output = ExpressionAsExecutable(expr)
    else:
      raise ParserException(expr.first_token, "This expression does nothing. Did you forget an assignment?")

  if include_semicolon:
    tokens.pop_expected(';')

  return output

def parse_for_loop(tokens):
  raise Exception("You left off here!")

class OpChainParser:
  def __init__(self, ops, next_parser_func):
    self.ops = list_to_lookup(ops)
    self.next_parser_func = next_parser_func
  
  def parse(self, tokens):
    expr = self.next_parser_func(tokens)
    next_value = tokens.peek_value()
    if self.ops.get(next_value) != None:
      expressions = [expr]
      ops = []
      while self.ops.get(next_value) != None:
        ops.append(tokens.pop())
        expressions.append(self.next_parser_func(tokens))
        next_value =  tokens.peek_value()
      expr = OpChain(expressions, ops)
    return expr

def parse_expression(tokens):
  return parse_ternary(tokens)

def parse_unaries(tokens):
  next_value = tokens.peek_value()
  if next_value in ('~', '!', '-', '++', '--'):
    op = tokens.pop()
    expr = parse_unaries(tokens)
    if next_value == '++' or next_value == '--':
      return InlineIncrement(op, op, expr, True, next_value == '++')
    return UnaryPrefix(op, expr)
  expr = parse_entity_with_suffix_chains(tokens)
  next_value = tokens.peek_value()
  if next_value in ('++', '--'):
    op = tokens.pop()
    return InlineIncrement(expr.first_token, op, expr, False, next_value == '++')
  return expr

def parse_entity_with_suffix_chains(tokens):
  expr = parse_entity(tokens)
  check_suffixes = True
  while check_suffixes:
    next_value = tokens.peek_value()
    if next_value == '.':
      dot = tokens.pop()
      field_name = tokens.pop()
      if field_name.token_type != 'WORD': raise ParserException(field_name, "Expected a valid field name but found '" + field_name.value + "'.")
      expr = DotField(expr, dot, field_name)
    elif next_value == '(':
      open_paren = tokens.pop()
      args = []
      while not tokens.pop_if_present(')'):
        if len(args) > 0:
          tokens.pop_expected(',')
        args.append(parse_expression(tokens))
      expr = FunctionInvocation(expr, open_paren, args)
    elif next_value == '[':
      open_bracket = tokens.pop()
      index_value = parse_expression(tokens)
      expr = BracketIndex(expr, open_bracket, index_value)
    else:
      check_suffixes = False
  return expr

def parse_entity(tokens):
  if tokens.is_next('('):
    tokens.pop_expected('(')
    expr = parse_expression(tokens)
    tokens.pop_expected(')')
    return expr

  next_token = tokens.peek()
  if next_token == None: raise tokens.eof()
  next_value = next_token.value
  next_type = next_token.token_type

  if next_type == 'KEYWORD':
    if next_type in ('true', 'false'):
      tokens.pop()
      return BooleanConstant(next_token, token_value == 'true')
    if next_type == 'null':
      return NullConstant(next_token)
    raise Exception(next_token, "Unexpected usage of '" + next_value + "'.")

  if next_type == 'WORD':
    tokens.pop()
    return Variable(next_token, next_value)
  
  if next_type == 'FLOAT':
    tokens.pop()
    float_value = None
    try:
      float_value = float(next_value)
    except:
      raise ParserException(next_token, "Invalid expression (presumed to be a float): '" + next_value + "'.")
    return FloatConstant(next_token, float_value)
  
  if next_type == 'NUMBER':
    tokens.pop()
    int_value = None
    if next_value[:2] == '0x':
      try:
        int_value = int(next_value[2:])
      except:
        raise ParserException(next_token, "Invalid expression (presumed to be a hexadecimal integer): '" + next_value + "'.")
    else:
      try:
        int_value = int(next_value)
      except:
        raise ParserException(next_token, "Invalid expression (presumed to be a decimal integer): '" + next_value + "'.")
    return IntegerConstant(next_token, int_value)
  
  if next_type == 'STRING':
    tokens.pop()
    str_value = string_literal_to_value(next_token, next_value[1:-1])
    return StringConstant(next_token, str_value)
  
  raise Exception(tokens.pop(), "Unexpected token: '" + next_value + "'.")

parse_multiplication = OpChainParser(['*', '/', '%'], parse_unaries).parse
parse_addition = OpChainParser(['+', '-'], parse_multiplication).parse
parse_bitwise_op = OpChainParser(['<<', '>>'], parse_addition).parse
parse_inequality = OpChainParser(['<', '>', '<=', '>='], parse_bitwise_op).parse
parse_equality = OpChainParser(['==', '!='], parse_inequality).parse
parse_bitwise_op = OpChainParser(['&', '|', '^'], parse_equality).parse
parse_boolean_combinator = OpChainParser(['&&', '||'], parse_bitwise_op).parse
parse_null_coalescer = OpChainParser(['??'], parse_boolean_combinator).parse

def parse_ternary(tokens):
  root = parse_null_coalescer(tokens)
  if not tokens.is_next('?'):
    return root
  
  question_mark = tokens.pop_expected('?')
  true_expr = parse_ternary(tokens)
  tokens.pop_expected(':')
  false_expr = parse_ternary(tokens)
  return TernaryExpression(root, question_mark, true_expr, false_expr)
