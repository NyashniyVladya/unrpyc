# License
# Copyright (c) 2008, Armin Ronacher
# All rights reserved.

# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:

# - Redistributions of source code must retain the above copyright notice, this list of
#   conditions and the following disclaimer.
# - Redistributions in binary form must reproduce the above copyright notice, this list of
#   conditions and the following disclaimer in the documentation and/or other materials
#   provided with the distribution.
# - Neither the name of the <ORGANIZATION> nor the names of its contributors may be used to
#   endorse or promote products derived  from this software without specific prior written
#   permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
# IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF
# THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# Taken from http://github.com/jonathaneunice/codegen

"""
    codegen
    ~~~~~~~

    Extension to ast that allow ast -> python code generation.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: BSD.
"""

# Updated ton contain latest pull requests from Doboy, jbremer,
# gemoe100, and cwa-, even though those have not been pulled into
# andreif's repo

from ast import *

def to_source(node, indent_with=' ' * 4, add_line_information=False, correct_line_numbers=False):
    """This function can convert a node tree back into python sourcecode.
    This is useful for debugging purposes, especially if you're dealing with
    custom asts not generated by python itself.

    It could be that the sourcecode is evaluable when the AST itself is not
    compilable / evaluable.  The reason for this is that the AST contains some
    more data than regular sourcecode does, which is dropped during
    conversion.

    Each level of indentation is replaced with `indent_with`.  Per default this
    parameter is equal to four spaces as suggested by PEP 8, but it might be
    adjusted to match the application's styleguide.

    If `add_line_information` is set to `True` comments for the line numbers
    of the nodes are added to the output.  This can be used to spot wrong line
    number information of statement nodes.
    """
    if correct_line_numbers:
        if hasattr(node, "lineno"):
            return SourceGenerator(indent_with, add_line_information, True, node.lineno).process(node)
        else:
            return SourceGenerator(indent_with, add_line_information, True).process(node)
    else:
        return SourceGenerator(indent_with, add_line_information).process(node)


class SourceGenerator(NodeVisitor):
    """This visitor is able to transform a well formed syntax tree into python
    sourcecode.  For more details have a look at the docstring of the
    `node_to_source` function.
    """

    COMMA = ', '
    COLON = ': '
    ASSIGN = ' = '
    SEMICOLON = '; '

    BOOLOP_SYMBOLS = {
        And:        (' and ', 4),
        Or:         (' or ',  3)
    }

    BINOP_SYMBOLS = {
        Add:        (' + ',  11),
        Sub:        (' - ',  11),
        Mult:       (' * ',  12),
        Div:        (' / ',  12),
        FloorDiv:   (' // ', 12),
        Mod:        (' % ',  12),
        Pow:        (' ** ', 14),
        LShift:     (' << ', 10),
        RShift:     (' >> ', 10),
        BitOr:      (' | ',  7),
        BitAnd:     (' & ',  9),
        BitXor:     (' ^ ',  8)
    }

    CMPOP_SYMBOLS = {
        Eq:         (' == ',     6),
        Gt:         (' > ',      6),
        GtE:        (' >= ',     6),
        In:         (' in ',     6),
        Is:         (' is ',     6),
        IsNot:      (' is not ', 6),
        Lt:         (' < ',      6),
        LtE:        (' <= ',     6),
        NotEq:      (' != ',     6),
        NotIn:      (' not in ', 6)
    }

    UNARYOP_SYMBOLS = {
        Invert:     ('~',    13),
        Not:        ('not ', 5),
        UAdd:       ('+',    13),
        USub:       ('-',    13)
    }

    BLOCK_NODES = (If, For, While, With, TryExcept, TryFinally,
                   FunctionDef, ClassDef)

    def __init__(self, indent_with, add_line_information=False, correct_line_numbers=False, line_number=1):
        self.result = []
        self.indent_with = indent_with
        self.add_line_information = add_line_information
        self.indentation = 0
        self.new_lines = 0

        self.precedence_stack = [0]
        self.precedence_ltr = [None]

        self.correct_line_numbers = correct_line_numbers
        # The current line number we *think* we are on. As in it's most likely
        # the line number of the last node we passed which can differ when
        # the ast is broken
        self.line_number = line_number
        # Can we insert a newline here without having to escape it?
        # (are we between delimiting characters)
        self.can_newline = False
        # After a colon (but before a newline or another statement) we don't
        # have to insert a semicolon
        self.after_block = True
        # Should a newline be forced the next opportunity for one (this can
        # happen because we're at the end of a block, before a statement having
        # a block, or the first line of a statement having a block if said block
        # contains a block-having statement anywhere)
        self.force_newline = False

    def process(self, node):
        self.visit(node)
        result = ''.join(self.result)
        self.result = []
        return result

    # Precedence management

    def prec_start(self, value, ltr=None):
        if value < self.precedence_stack[-1]:
            self.write('(')
        self.precedence_ltr.append(ltr)
        if ltr == False:
            value += 1
        self.precedence_stack.append(value)

    def prec_middle(self):
        if self.precedence_ltr[-1]:
            self.precedence_stack[-1] += 1
        elif self.precedence_ltr[-1] is False:
            self.precedence_stack[-1] -= 1

    def prec_end(self):
        if self.precedence_ltr.pop():
            self.precedence_stack[-1] -= 1
        if self.precedence_stack.pop() < self.precedence_stack[-1]:
            self.write(')')

    # convenience functions

    def write(self, x):
        if self.new_lines:
            if self.result or self.correct_line_numbers:
                self.result.append('\n' * self.new_lines)
            self.result.append(self.indent_with * self.indentation)
            self.new_lines = 0
        self.result.append(x)

    def newline(self, node=None, extra=0, body=False):
        if not self.correct_line_numbers:
            self.new_lines = max(self.new_lines, 1 + extra)
            if node is not None and self.add_line_information:
                self.write('# line: %s' % node.lineno)
                self.new_lines = 1
        else:
            if extra:
                #Ignore extra
                return
            # Statements which have a block
            elif node is None:
                # else or finally statements which do not have a recorded line number
                # Assume they're right after the previous statement
                # alternatively it might be possible to place them before the next statement
                self.new_lines = 1
                self.line_number += 1

            elif body:
                self.new_lines = node.lineno - self.line_number + self.new_lines
                if self.new_lines <= 0 and self.result:
                    # can't have block-having statements on the same line as the previous statement
                    # unless it's the first line
                    self.new_lines = 1
                self.line_number = node.lineno

            elif node is not None:
                self.new_lines = node.lineno - self.line_number + self.new_lines
                if self.new_lines < 0:
                    # Weird ast with linenumbers going back in time. lets
                    # not do that
                    self.new_lines = 0
                self.line_number = node.lineno

                if not self.new_lines:
                    # If we're not following a block start we need a semicolon
                    if self.force_newline:
                        self.new_lines = 1
                    elif not self.after_block:
                        self.write(self.SEMICOLON)
                    elif self.result:
                        self.write(' ')
                self.after_block = False
                self.force_newline = False

    def maybe_break(self, node):
        if self.correct_line_numbers:
            # can't break a line before anything has even been printed in it
            # This can be triggered by things like (\n1)
            new_lines = self.new_lines
            if self.new_lines:
                self.write('')

            if node.lineno > self.line_number:
                self.newline(node)
                if not self.can_newline:
                    # Syntactically we're not allowed to newline here,
                    # but since evidently a newline happened here
                    # use an escaped newline to correct for it
                    # This can happen when statemens are parenthesized
                    # Just to cross newline boundaries, but that's
                    # impossible to distinguish and hard to parse
                    self.result.append('\\\n' * self.new_lines)
                    if not new_lines:
                        # if something was already printed we can indent safely
                        self.result.append(self.indent_with * (self.indentation + 1))
                else:
                    self.result.append('\n' * self.new_lines)
                    self.result.append(self.indent_with * (self.indentation + 1))
                self.new_lines = 0

    def body(self, statements):
        self.force_newline = (any(isinstance(i, self.BLOCK_NODES) for i in statements) or
                              (any(i.lineno > self.line_number for i in statements) and
                              self.correct_line_numbers))
        self.indentation += 1
        self.after_block = not self.force_newline
        for stmt in statements:
            self.visit(stmt)
        self.indentation -= 1
        self.force_newline = True
        self.after_block = False # do empty blocks even exist?

    def body_or_else(self, node):
        self.body(node.body)
        if node.orelse:
            self.newline(body=True)
            self.write('else:')
            self.body(node.orelse)

    def signature(self, node):
        want_comma = []
        b = self.can_newline
        self.can_newline = True
        def write_comma():
            if want_comma:
                self.write(self.COMMA)
            else:
                want_comma.append(True)

        padding = [None] * (len(node.args) - len(node.defaults))
        for arg, default in zip(node.args, padding + node.defaults):
            write_comma()
            if default is not None:
                self.maybe_break(default)
            self.visit(arg)
            if default is not None:
                self.write('=')
                self.visit(default)
        if node.vararg is not None:
            write_comma()
            self.write('*' + node.vararg)
        if node.kwarg is not None:
            write_comma()
            self.write('**' + node.kwarg)
        self.can_newline = b

    def decorators(self, node):
        for decorator in node.decorator_list:
            self.force_newline = True
            self.newline(decorator)
            self.write('@')
            self.visit(decorator)

    # Module
    def visit_Module(self, node):
        self.generic_visit(node)
        self.write('\n')
        self.line_number += 1

    # Statements

    def visit_Assert(self, node):
        self.newline(node)
        self.write('assert ')
        self.visit(node.test)
        if node.msg:
            self.write(self.COMMA)
            self.visit(node.msg)

    def visit_Assign(self, node):
        self.newline(node)
        for idx, target in enumerate(node.targets):
            if isinstance(target, Tuple):
                self.visit_Tuple(target, False)
            else:
                self.visit(target)
            self.write(self.ASSIGN)
        self.visit(node.value)

    def visit_AugAssign(self, node):
        self.newline(node)
        self.visit(node.target)
        self.write(self.BINOP_SYMBOLS[type(node.op)][0].strip() + '=')
        self.visit(node.value)

    def visit_ImportFrom(self, node):
        self.newline(node)
        self.write('from ')
        self.write('%s%s' % ('.' * node.level, node.module))
        self.write(' import ')
        for idx, item in enumerate(node.names):
            if idx:
                self.write(self.COMMA)
            self.write(item.name)
            if item.asname is not None:
                self.write(' as ')
                self.write(item.asname)

    def visit_Import(self, node):
        self.newline(node)
        self.write('import ')
        for idx, item in enumerate(node.names):
            if idx:
                self.write(self.COMMA)
            self.visit(item)

    def visit_Exec(self, node):
        self.newline(node)
        self.write('exec ')
        self.visit(node.body)
        if node.globals:
            self.write(' in ')
            self.visit(node.globals)
        if node.locals:
            self.write(self.COMMA)
            self.visit(node.locals)

    def visit_Expr(self, node):
        self.newline(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.newline(extra=1)
        self.decorators(node)
        self.newline(node, body=True)
        self.write('def %s(' % node.name)
        self.signature(node.args)
        self.write('):')
        self.body(node.body)

    def visit_ClassDef(self, node):
        have_args = []
        def paren_or_comma():
            if have_args:
                self.write(self.COMMA)
            else:
                have_args.append(True)
                self.write('(')

        self.newline(extra=2)
        self.decorators(node)
        self.newline(node, body=True)
        self.write('class %s' % node.name)
        self.can_newline = True
        for base in node.bases:
            paren_or_comma()
            self.visit(base)
        # XXX: the if here is used to keep this module compatible
        #      with python 2.6.
        if hasattr(node, 'keywords'):
            for keyword in node.keywords:
                paren_or_comma()
                self.maybe_break(keyword.value)
                self.write(keyword.arg + '=')
                self.visit(keyword.value)
            if node.starargs is not None:
                paren_or_comma()
                self.maybe_break(node.starargs)
                self.write('*')
                self.visit(node.starargs)
            if node.kwargs is not None:
                paren_or_comma()
                self.maybe_break(node.kwargs)
                self.write('**')
                self.visit(node.kwargs)
        self.can_newline = False
        self.write(have_args and '):' or ':')
        self.body(node.body)

    def visit_If(self, node):
        self.newline(node, body=True)
        self.write('if ')
        self.visit(node.test)
        self.write(':')
        self.body(node.body)
        while True:
            else_ = node.orelse
            if len(else_) == 1 and isinstance(else_[0], If):
                node = else_[0]
                self.newline(node.test, body=True)
                self.write('elif ')
                self.visit(node.test)
                self.write(':')
                self.body(node.body)
            else:
                if else_:
                    self.newline(body=True)
                    self.write('else:')
                    self.body(else_)
                break

    def visit_For(self, node):
        self.newline(node, body=True)
        self.write('for ')
        if isinstance(node.target, Tuple):
            self.visit_Tuple(node.target, False)
        else:
            self.visit(node.target)
        self.write(' in ')
        self.visit(node.iter)
        self.write(':')
        self.body_or_else(node)

    def visit_While(self, node):
        self.newline(node, body=True)
        self.write('while ')
        self.visit(node.test)
        self.write(':')
        self.body_or_else(node)

    def visit_With(self, node):
        self.newline(node, body=True)
        self.write('with ')
        self.visit(node.context_expr)
        if node.optional_vars is not None:
            self.write(' as ')
            self.visit(node.optional_vars)
        self.write(':')
        self.body(node.body)

    def visit_Pass(self, node):
        self.newline(node)
        self.write('pass')

    def visit_Print(self, node):
        # XXX: python 2.6 only
        self.newline(node)
        self.write('print ')
        want_comma = False
        if node.dest is not None:
            self.write(' >> ')
            self.visit(node.dest)
            want_comma = True
        for value in node.values:
            if want_comma:
                self.write(self.COMMA)
            self.visit(value)
            want_comma = True
        if not node.nl:
            self.write(',')

    def visit_Delete(self, node):
        self.newline(node)
        self.write('del ')
        for idx, target in enumerate(node.targets):
            if idx:
                self.write(self.COMMA)
            self.visit(target)

    def visit_TryExcept(self, node):
        self.newline(node, body=True)
        self.write('try:')
        self.body(node.body)
        for handler in node.handlers:
            self.visit(handler)
        if node.orelse:
            self.newline(body=True)
            self.write('else:')
            self.body(node.orelse)

    def visit_ExceptHandler(self, node):
        self.newline(node, body=True)
        self.write('except')
        if node.type:
            self.write(' ')
            self.visit(node.type)
        if node.name:
            self.write(self.COMMA)
            self.visit(node.name)
        self.write(':')
        self.body(node.body)

    def visit_TryFinally(self, node):
        if len(node.body) == 1 and isinstance(node.body[0], TryExcept):
            self.visit_TryExcept(node.body[0])
        else:
            self.newline(node, body=True)
            self.write('try:')
            self.body(node.body)
        self.newline(body=True)
        self.write('finally:')
        self.body(node.finalbody)

    def visit_Global(self, node):
        self.newline(node)
        self.write('global ' + self.COMMA.join(node.names))

    def visit_Nonlocal(self, node):
        self.newline(node)
        self.write('nonlocal ' + self.COMMA.join(node.names))

    def visit_Return(self, node):
        self.newline(node)
        if node.value is not None:
            self.write('return ')
            self.visit(node.value)
        else:
            self.write('return')

    def visit_Break(self, node):
        self.newline(node)
        self.write('break')

    def visit_Continue(self, node):
        self.newline(node)
        self.write('continue')

    def visit_Raise(self, node):
        # XXX: Python 2.6 / 3.0 compatibility
        self.newline(node)
        if hasattr(node, 'exc') and node.exc is not None:
            self.write('raise ')
            self.visit(node.exc)
            if node.cause is not None:
                self.write(' from ')
                self.visit(node.cause)
        elif hasattr(node, 'type') and node.type is not None:
            self.write('raise ')
            self.visit(node.type)
            if node.inst is not None:
                self.write(self.COMMA)
                self.visit(node.inst)
            if node.tback is not None:
                self.write(self.COMMA)
                self.visit(node.tback)
        else:
            self.write('raise')

    # Expressions

    def visit_Attribute(self, node):
        # Edge case: due to the use of \d*[.]\d* for floats \d*[.]\w*, you have
        # to put parenthesis around an integer literal do get an attribute from it
        if isinstance(node.value, Num):
            self.write('(')
            self.visit(node.value)
            self.write(')')
        else:
            self.prec_start(15)
            self.visit(node.value)
            self.prec_end()
        self.write('.' + node.attr)

    def visit_Call(self, node):
        want_comma = []
        def write_comma():
            if want_comma:
                self.write(self.COMMA)
            else:
                want_comma.append(True)
        self.prec_start(15)
        self.visit(node.func)
        self.prec_end()
        self.write('(')
        b = self.can_newline
        self.can_newline = True
        for arg in node.args:
            write_comma()
            self.maybe_break(arg)
            self.visit(arg)
        for keyword in node.keywords:
            write_comma()
            self.maybe_break(keyword.value)
            self.write(keyword.arg + '=')
            self.visit(keyword.value)
        if node.starargs is not None:
            write_comma()
            self.maybe_break(node.starargs)
            self.write('*')
            self.visit(node.starargs)
        if node.kwargs is not None:
            write_comma()
            self.maybe_break(node.kwargs)
            self.write('**')
            self.visit(node.kwargs)
        self.can_newline = b
        self.write(')')

    def visit_Name(self, node):
        self.maybe_break(node)
        self.write(node.id)

    def visit_Str(self, node):
        self.maybe_break(node)
        self.write(repr(node.s))

    def visit_Bytes(self, node):
        self.maybe_break(node)
        self.write(repr(node.s))

    def visit_Num(self, node):
        self.maybe_break(node)
        self.write(repr(node.n))

    def visit_Tuple(self, node, guard=True):
        # Don't use extra parenthesis for "for" statement unpacking
        # and other things
        if guard:
            self.write('(')
            b = self.can_newline
            self.can_newline = True
        idx = -1
        for idx, item in enumerate(node.elts):
            if idx:
                self.write(self.COMMA)
            self.visit(item)
        if guard:
            self.write(idx and ')' or ',)')
            self.can_newline = b

    def _sequence_visit(left, right): # pylint: disable=E0213
        def visit(self, node):
            self.write(left)
            b = self.can_newline
            self.can_newline = True
            for idx, item in enumerate(node.elts):
                if idx:
                    self.write(self.COMMA)
                self.visit(item)
            self.can_newline = b
            self.write(right)
        return visit

    visit_List = _sequence_visit('[', ']')
    visit_Set = _sequence_visit('{', '}')

    def visit_Dict(self, node):
        self.write('{')
        b = self.can_newline
        self.can_newline = True
        for idx, (key, value) in enumerate(zip(node.keys, node.values)):
            if idx:
                self.write(self.COMMA)
            self.maybe_break(value)
            self.visit(key)
            self.write(self.COLON)
            self.visit(value)
        self.can_newline = b
        self.write('}')

    def visit_BinOp(self, node):
        self.maybe_break(node)
        symbol, precedence = self.BINOP_SYMBOLS[type(node.op)]
        self.prec_start(precedence, type(node.op) != Pow)
        self.visit(node.left)
        self.write(symbol)
        self.prec_middle()
        self.visit(node.right)
        self.prec_end()

    def visit_BoolOp(self, node):
        self.maybe_break(node)
        symbol, precedence = self.BOOLOP_SYMBOLS[type(node.op)]
        self.prec_start(precedence)
        for idx, value in enumerate(node.values):
            if idx:
                self.write(symbol)
            self.visit(value)
        self.prec_end()

    def visit_Compare(self, node):
        self.maybe_break(node)
        self.prec_start(6)
        self.visit(node.left)
        for op, right in zip(node.ops, node.comparators):
            self.write(self.CMPOP_SYMBOLS[type(op)][0])
            self.visit(right)
        self.prec_end()

    def visit_UnaryOp(self, node):
        symbol, precedence = self.UNARYOP_SYMBOLS[type(node.op)]
        self.prec_start(precedence)
        self.write(symbol)
        self.visit(node.operand)
        self.prec_end()

    def visit_Subscript(self, node):
        self.maybe_break(node)
        self.prec_start(15)
        self.visit(node.value)
        self.prec_end()
        self.write('[')
        b = self.can_newline
        self.can_newline = True
        self.visit(node.slice)
        self.can_newline = b
        self.write(']')

    def visit_Slice(self, node):
        if node.lower is not None:
            self.visit(node.lower)
        self.write(':')
        if node.upper is not None:
            self.visit(node.upper)
        if node.step is not None:
            self.write(':')
            if not (isinstance(node.step, Name) and node.step.id == 'None'):
                self.visit(node.step)

    def visit_ExtSlice(self, node):
        for idx, item in enumerate(node.dims):
            if idx:
                self.write(self.COMMA)
            self.visit(item)

    def visit_Yield(self, node):
        self.maybe_break(node)
        if node.value is not None:
            self.write('yield ')
            self.visit(node.value)
        else:
            self.write('yield')

    def visit_Lambda(self, node):
        self.maybe_break(node)
        self.prec_start(1)
        self.write('lambda ')
        self.signature(node.args)
        self.write(self.COLON)
        self.visit(node.body)
        self.prec_end()

    def visit_Ellipsis(self, node):
        self.maybe_break(node)
        self.write('Ellipsis')

    def _generator_visit(left, right): # pylint: disable=E0213
        def visit(self, node):
            self.maybe_break(node)
            self.write(left)
            b = self.can_newline
            self.can_newline = True
            self.visit(node.elt)
            for comprehension in node.generators:
                self.visit(comprehension)
            self.can_newline = b
            self.write(right)
        return visit

    visit_ListComp = _generator_visit('[', ']')
    visit_GeneratorExp = _generator_visit('(', ')')
    visit_SetComp = _generator_visit('{', '}')

    def visit_DictComp(self, node):
        self.maybe_break(node)
        self.write('{')
        b = self.can_newline
        self.can_newline = True
        self.visit(node.key)
        self.write(self.COLON)
        self.visit(node.value)
        for comprehension in node.generators:
            self.visit(comprehension)
        self.can_newline = b
        self.write('}')

    def visit_IfExp(self, node):
        self.maybe_break(node)
        self.prec_start(2, False)
        self.visit(node.body)
        self.write(' if ')
        self.visit(node.test)
        self.prec_middle()
        self.write(' else ')
        self.visit(node.orelse)
        self.prec_end()

    def visit_Starred(self, node):
        self.maybe_break(node)
        self.write('*')
        self.visit(node.value)

    def visit_Repr(self, node):
        # XXX: python 2.6 only
        self.maybe_break(node)
        self.write('`')
        self.visit(node.value)
        self.write('`')

    # Helper Nodes

    def visit_alias(self, node):
        self.write(node.name)
        if node.asname is not None:
            self.write(' as ' + node.asname)

    def visit_comprehension(self, node):
        self.maybe_break(node.target)
        self.write(' for ')
        self.visit(node.target)
        self.write(' in ')
        self.visit(node.iter)
        for if_ in node.ifs:
            self.write(' if ')
            self.visit(if_)
