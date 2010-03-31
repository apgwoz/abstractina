from collections import namedtuple

MachineState = namedtuple('MachineState', 'S E C D')
Cons = namedtuple('Cons', 'car cdr')
Closure = namedtuple('Closure', 'frame env')
Instruction = namedtuple('Instruction', 'op_code args')


class UnknownInstructionError(Exception):
    pass

class HaltException(Exception):
    pass

class Environment(object):

    __slots__ = ('_level', '_parent',)

    def __init__(self, values=None, parent=None):
        self._parent = parent
        self._level = values or []

    def new_level(self, values=None):
        new_env = Environment(values=values, parent=self)
        return new_env

    def replace_level(self, values):
        self._level = values
        return self

    def __getslice__(self, levels_up, offset):
        this = self

        while levels_up > 0 and this != None:
            this = this._parent
            levels_up -= 1

        return this._level[offset]

    def __getitem__(self, i):
        print "called getitem", i

    def __repr__(self):
        return '[%r %r]' % (self._level, self._parent)


class Stack(object):

    __slots__ = ('_parent', '_type', '_item',)

    def __init__(self, parent=None):
        self._parent = parent
        self._type = None
        self._item = None

    def __len__(self):
        i = 0
        this = self
        while this._parent != None:
            i += 1
            this = this._parent
        return i

    def peek(self):
        return (self._type, self._item)

    def pop(self, type=None):
        if self._type == type:
            return self._item, self._parent or Stack()
        raise ValueError("Couldn't pop value of type '%s'" % type)

    def push(self, *args):
        new_stack = Stack(parent=self)
        if len(args) == 2:
            new_stack._type = args[0]
            new_stack._item = args[1]
        else:
            new_stack._type = None
            new_stack._item = args[0]
        return new_stack

    def __repr__(self):
        return '[(%s %r) %r]' % (self._type, self._item, self._parent)


instructions = {
    'n': 'NIL',
    'd': 'DUM',
    'c': 'LDC',
    'l': 'LD',
    'f': 'LDF',
    'j': 'JOIN',
    's': 'SEL',
    'a': 'AP',
    'p': 'RAP',
    'r': 'RET',
    '.': 'CONS',
    '(': 'CAR',
    ')': 'CDR',
    '+': 'ADD',
    '*': 'MUL',
    '=': 'EQ',
    '!': 'HALT',
    'nil': 'NIL',
    'dum': 'DUM',
    'ldc': 'LDC',
    'ld': 'LD',
    'ldf': 'LDF',
    'join': 'JOIN',
    'sel': 'SEL',
    'ap': 'AP',
    'ret': 'RET',
    'cons': 'CONS',
    'car': 'CAR',
    'cdr': 'CDR',
    'add': 'ADD',
    'mul': 'MUL',
    'eq': 'eq',
    'HALT': 'HALT',
}


class SECDMachine(object):

    def execute(self, instruction, state):
        if len(instruction) == 2:
            op_code, args = instruction
        else:
            op_code = instruction[0]
            args = None
        
        if op_code in ('!', 'HALT'): # halt state
            raise HaltException()
        operator = self.get_operator(op_code)

        new_args = list((args or [])) + [state]
        return operator(*new_args)

    def get_operator(self, op_code):
        print "op_code: ", op_code
        name = instructions.get(op_code, None)
        print " name: ", name
        if not name:
            raise UnknownInstructionError("No instruction named '%s'" \
                                              % op_code)
        return getattr(self, 'op_%s' % name)

    def run(self, state):
        try:
            while len(state.C):
                instruction = state.C[0]
                state = self.execute(instruction,
                                     MachineState(state.S,
                                                  state.E,
                                                  state.C[1:],
                                                  state.D))
                self.dump_state(state)
                raw_input('<hit enter for next next>')
        except HaltException:
            print ".HALTED"

    def dump_state(self, state):
        print 'S: ', state.S
        print 'E: ', state.E
        print 'C: ', state.C
        print 'D: ', state.D

    def op_NIL(self, state):
        """nil pushes a nil pointer onto the stack"""
        new_stack = state.S.push('value', None)
        return MachineState(new_stack, state.E, state.C, state.D)

    def op_LDC(self, constant, state):
        """ldc pushes a constant argument onto the stack"""
        new_stack = state.S.push('value', constant)
        return MachineState(new_stack, state.E, state.C, state.D)

    def op_LD(self, p, state):
        """ld pushes the value of a variable onto the stack.

        The variable is indicated by the argument, a pair. The pair's car
        specifies the level, the cdr the position. So "(1 . 3)" gives the
        current function's (level 1) third parameter.
        """
        value = state.E[p.car:p.cdr]
        new_stack = state.S.push('value', value)
        return MachineState(new_stack, state.E, state.C, state.D)

    def op_LDF(self, frame, state):
        """ldf takes one list argument representing a function. It
        constructs a closure (a pair containing the function and the current
        environment) and pushes that onto the stack.
        """
        new_stack = state.S.push('closure', Closure(frame, state.E,))
        return MachineState(new_stack, state.E, state.C, state.D)

    def op_SEL(self, consequent, alternate, state):
        """sel expects two list arguments, and pops a value from the stack.

        The first list is executed if the popped value was non-nil,
        the second list otherwise. Before one of these list pointers
        is made the new C, a pointer to the instruction following sel
        is saved on the dump.
        """
        conditional, new_stack = state.S.pop('value')
        new_dump = state.D.push(state.C)
        new_code = consequent if is_null(condtional) else alternate
        return MachineState(new_stack, state.E, new_code, state.D)

    def op_JOIN(self, state):
        """join pops a list reference from the dump and makes this the
        new value of C.

        This instruction occurs at the end of both alternatives of a
        sel.
        """
        new_code, new_dump = state.D.pop()
        return MachineState(state.S, state.E, new_code, new_dump)

    def op_AP(self, state):
        """ap pops a closure and a list of parameter values from the stack.

        The closure is applied to the parameters by installing its
        environment as the current one, pushing the parameter list in
        front of that, clearing the stack, and setting C to the
        closure's function pointer. The previous values of S, E, and
        the next value of C are saved on the dump.
        """
        new_dump = state.D.push(state.S).push(state.E).push(state.C)
        closure, new_stack = state.S.pop('closure')
        parameters, new_stack = state.S.pop('value')
        new_stack = state.S.clear()
        new_env = closure[1].new_level(parameters)
        return MachineState(new_stack, new_env, closure[0], new_dump)

    def op_RAP(self, state):
        """rap works like ap, only that it replaces an occurrence of a
        dummy environment with the current one, thus making recursive
        functions possible
        """
        new_dump = state.D.push(state.S).push(state.E).push(state.C)
        closure, new_stack = state.S.pop('closure')
        parameters, new_stack = state.S.pop('value')
        new_stack = state.S.clear()
        new_env = closure[1].replace_level(parameters)
        return MachineState(new_stack, new_env, closure[0], new_dump)

    def op_RET(self, state):
        """ret pops one return value from the stack, restores S, E, and C
        from the dump, and pushes the return value onto the now-current stack.
        """
        old_code, new_dump = state.D.pop()
        old_env, new_dump = state.D.pop()
        old_stack, new_dump = state.D.pop()

        return MachineStack(old_stack, old_env, old_code, new_dump)

    def op_DUM(self, state):
        """dum pushes a "dummy", an empty list, in front of the environment
        list.
        """
        new_env = state.E.new_level()
        return MachineState(state.S, new_env, state.C, state.D)
        
    def op_CONS(self, state):
        """cons pushes a cons to the stack made from the 2 top values of the
        stack. 

        The car of the cons will be the top value on the stack. 
        The cdr of the cons will be the second value on the stack.
        """
        car, s = state.S.pop('value')
        cdr, s = s.pop('value')
        
        new_stack = s.push('value', Cons(car, cdr))
        return MachineState(new_stack, state.E, state.C, state.D)

    def op_CAR(self, state):
        """car pushes the car of a the cons on the top of the stack
        """
        cons, s = state.S.pop('value')
        if not isinstance(cons, Cons):
            raise ValueError("top value of the stack not a cons")
        new_stack = s.push('value', cons.car)
        return MachineState(new_stack, state.E, state.C, state.D)

    def op_CDR(self, state):
        """car pushes the car of a the cons on the top of the stack
        """
        cons, s = state.S.pop('value')
        if not isinstance(cons, Cons):
            raise ValueError("top value of the stack not a cons")
        new_stack = s.push('value', cons.cdr)
        return MachineState(new_stack, state.E, state.C, state.D)

    def op_ADD(self, state):
        """add pushes the sum of the top two values back onto the stack
        """
        op1, s = state.S.pop('value')
        op2, s = s.pop('value')
        if not (isinstance(op1, int) and isinstance(op2, int)):
            raise ValueError("can't take the sum of non-integers")
        new_stack = s.push('value', op1 + op2)
        return MachineState(new_stack, state.E, state.C, state.D)

    def op_MUL(self, state):
        """mul pushes the product of the top two values back onto the stack
        """
        op1, s = state.S.pop('value')
        op2, s = s.pop('value')
        if not (isinstance(op1, int) and isinstance(op2, int)):
            raise ValueError("can't take the product of non-integers")
        new_stack = s.push('value', op1 + op2)
        return MachineState(new_stack, state.E, state.C, state.D)

    def op_EQ(self, state):
        """eq pushes a non nil value to the stack if the top 2 stack 
        values are equal. pushes nil (None) otherwise.
        """
        op1, s = state.S.pop('value')
        op2, s = s.pop('value')
        if op1 == op2:
            new_value = 1
        else:
            new_value = None
        new_stack = new_stack.push('value', new_value)
        return MachineState(new_stack, state.E, state.C, state.D)
