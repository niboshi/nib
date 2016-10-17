import sys
import abc
import logging
import collections

from .environment import EvaluationEnvironment


class QueryTokenizer:
    def __init__(self, str, **kwargs):
        verbose = kwargs.pop('verbose', False)
        assert len(kwargs) == 0

        self.tokens = []
        while True:
            tok,str = self.__readToken(str)
            if len(tok) == 0:
                break

            if verbose:
                sys.stderr.write("TOKEN: %s\n" % tok)

            self.tokens.append(tok)

    def __readToken(self, text):
        QUOTE_SINGLE = 1
        QUOTE_DOUBLE = 2
        t = text
        i = 0
        while i < len(t) and t[i] == ' ':
            i += 1
        quote = False
        t0 = ''
        while True:
            if i == len(t):
                if quote:
                    raise Exception("Query syntax error: unclosed quotes")
                else:
                    break
            elif t[i] == '"':
                if not quote:
                    quote = QUOTE_DOUBLE
                elif quote == QUOTE_SINGLE:
                    t0 += t[i]
                elif quote == QUOTE_DOUBLE:
                    quote = False
                else: assert False
            elif t[i] == '\'':
                if not quote:
                    quote = QUOTE_SINGLE
                elif quote == QUOTE_SINGLE:
                    quote = False
                elif quote == QUOTE_DOUBLE:
                    t0 += t[i]
                else: assert False
            elif t[i] == '\\' and quote != QUOTE_SINGLE:
                i += 1
                if i == len(t):
                    raise Exception("Query syntax error: invalid escape")
                t0 += t[i]
            elif t[i] == ' ' and not quote:
                break
            else:
                t0 += t[i]
            i += 1
        t = t[i+1:]
        return t0,t

    def get(self):
        return self.tokens

class TreeNode(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, token):
        self.token = token
        self.parent = None
        self.childNodes = None
        pass

    def setChildNode(self, i, node):
        if self.childNodes is None:
            self.childNodes = [None] * i
        if len(self.childNodes) < i+1:
            self.childNodes += [None] * (i + 1 - len(self.childNodes))
        self.childNodes[i] = node
        node.parent = self

    def replaceChildNode(self, oldNode, newNode):
        self.setChildNode(
            self.childNodes.index(oldNode),
            newNode
        )

    def addChildNode(self, node):
        if self.childNodes is None:
            self.childNodes = [node]
        else:
            self.childNodes.append(node)
        node.parent = self

    def getLeafNodes(self):
        if self.childNodes is None or len(self.childNodes) == 0:
            yield self
        else:
            for childNode in self.childNodes:
                for leafNode in childNode.getLeafNodes():
                    yield leafNode

    def __str__(self):
        return self._to_str(True, show_parent=False)

    def __repr__(self):
        return self._to_str(False, show_parent=False)

    def _to_str(self, readable, indent=0, show_parent=True):
        if readable:
            next_indent = indent + 2
        else:
            next_indent = indent
        id_to_str = lambda x: '%04d' % (x % 10000)

        s = ['token={}'.format(self.token)]
        if self.childNodes is not None:
            for i,childNode in enumerate(self.childNodes):
                if childNode is None:
                    continue
                s.append('child{}={}'.format(i, childNode._to_str(readable, next_indent, show_parent=show_parent)))
        if show_parent and self.parent is not None:
            s.append('parent=%s' % id_to_str(id(self.parent)))

        s_indent  = ' ' * indent
        s_indent2 = ' ' * (indent + 2)
        if readable:
            s_start   = '%s%s{%s' % (s_indent, id_to_str(id(self)), '\n')
        else:
            s_start   = '%s%s{%s' % (s_indent, id_to_str(id(self)), ' ')

        if readable:
            s_content = ''.join('%s%s\n' % (s_indent2, str(_)) for _ in s)
        else:
            s_content = ''.join('%s%s ' % ('', str(_)) for _ in s)

        if readable:
            s_end     = '%s}%s' % (s_indent, '')
        else:
            s_end     = '%s}%s' % (s_indent, '')

        return s_start + s_content + s_end

    @abc.abstractmethod
    def is_fullfilled(self):
        pass

    def eval(self, env, source=None, positive=True):
        assert isinstance(env, EvaluationEnvironment)
        assert self.is_fullfilled()
        return self.eval_impl(env, source, positive)

    @abc.abstractmethod
    def eval_impl(self, env, source, positive):
        pass

class TextNode(TreeNode):
    def __init__(self, token):
        assert token[0] == 'text'
        super(TextNode, self).__init__(token)

    def is_fullfilled(self):
        return True

    def eval_impl(self, env, source, positive):
        return env.evalGenerator(self.token[1], source, positive)

class OperatorNode(TreeNode):
    def __init__(self, token, op):
        assert token[0] == 'op'
        super(OperatorNode, self).__init__(token)
        self.op = op

    def is_fullfilled(self):
        op = self.op
        if isinstance(op, BinaryOperator):
            return self.childNodes is not None and len(self.childNodes) == 2
        elif isinstance(op, UnaryOperator):
            return self.childNodes is not None and len(self.childNodes) == 1
        else:
            assert False, op

    def eval_impl(self, env, source, positive):
        op = self.op
        if isinstance(op, BinaryOperator):
            return op.eval(env, source, positive, self.childNodes[0], self.childNodes[1])
        elif isinstance(op, UnaryOperator):
            return op.eval(env, source, positive, self.childNodes[0])
        else:
            assert False, op
        pass


class Operator(object):
    __metaclass__ = abc.ABCMeta
    pass

class UnaryOperator(Operator):
    __metaclass__ = abc.ABCMeta

    def eval(self, env, source, positive, o1):
        assert isinstance(env, EvaluationEnvironment)
        return self.eval_impl(env, source, positive, o1)

    @abc.abstractmethod
    def eval_impl(self, env, source, positive, o1):
        pass


class Op_Root(UnaryOperator):
    def eval_impl(self, env, source, positive, o1):
        return o1.eval(env, source, positive)

class Op_Not(UnaryOperator):
    def eval_impl(self, env, source, positive, o1):
        if source is None:
            raise NotImplementedError()

        return o1.eval(env, source, not positive)

class BinaryOperator(Operator):
    __metaclass__ = abc.ABCMeta

    def eval(self, env, source, positive, o1, o2):
        assert isinstance(env, EvaluationEnvironment)
        ret = self.eval_impl(env, source, positive, o1, o2)
        assert isinstance(ret, collections.Iterable)
        return ret

    @abc.abstractmethod
    def eval_impl(self, env, source, positive, o1, o2):
        pass

class Op_And(BinaryOperator):
    def eval_impl(self, env, source, positive, o1, o2):
        if positive:
            return env.intersection(source, o1, o2, True, True)
        else:
            return env.union(source, o1, o2, False, False)

class Op_Subtract(BinaryOperator):
    def eval_impl(self, env, source, positive, o1, o2):
        if positive:
            return env.intersection(source, o1, o2, True, False)
        else:
            return env.union(source, o1, o2, False, True)

class Op_Or(BinaryOperator):
    def eval_impl(self, env, source, positive, o1, o2):
        if positive:
            return env.union(source, o1, o2, True, True)
        else:
            return env.intersection(source, o1, o2, False, False)

class Op_Pipe(BinaryOperator):
    def eval_impl(self, env, source, positive, o1, o2):
        if positive:
            return env.intersection(source, o1, o2, True, True)
        else:
            return env.union(source, o1, o2, False, False)
        return res

class QueryParser(object):
    def __init__(self, str):
        #--------------------------
        # Operator definition
        #--------------------------

        self.operators = [
            ('not',     0, Op_Not),
            ('-',       1, Op_Subtract),
            ('and',     1, Op_And),
            ('or',      1, Op_Or),
            ('|',       1, Op_Pipe),
            (None,   1000, Op_Root),
        ]
        self.operator_strs = [_[0] for _ in self.operators] + ['(', ')']

        self.op_sym_to_cls = {}
        for sym, pri, cls in self.operators:
            if sym is None:
                continue
            self.op_sym_to_cls[sym] = cls

        self.op_cls_to_prior = {}
        for sym, pri, cls in self.operators:
            self.op_cls_to_prior[cls] = pri

        #--------------------------
        # Build expression tree
        #--------------------------

        tokens = QueryTokenizer(str).get()
        tokens = self.__annotate(tokens)
        self.tree = self.__buildExpressionTree(tokens)

        pass

    def getTree(self):
        return self.tree

    def __annotate(self, tokens):
        import re
        newTokens = []
        for i in range(len(tokens)):
            tok = tokens[i]

            if tok in self.operator_strs:
                tok = ('op', tok)
            else:
                m = re.match(r'([-a-z0-5]+):(.*)', tok)
                if m is None:
                    action = tok
                    param = ""
                else:
                    action = m.group(1)
                    param  = m.group(2)

                tok = ('text', (action, param))

            newTokens.append(tok)

        return newTokens

    def __buildExpressionTree(self, tokens):
        node,end = self.__parseParenTree(tokens, 0, False)
        assert end == len(tokens)
        assert node is not None

        node = self.__optimizeTree(node)
        return node

    def __parseParenTree(self, tokens, start, allowClosingParen):
        lastNode = None

        def compareOperatorPriority(op1, op2):
            assert isinstance(op1, Operator)
            assert isinstance(op2, Operator)
            i1 = self.op_cls_to_prior[op1.__class__]
            i2 = self.op_cls_to_prior[op2.__class__]
            return i2 - i1


        i = start
        while i < len(tokens):
            token = tokens[i]
            tag,sym = token
            i += 1

            if tag == 'op':
                if sym == ')':
                    if not allowClosingParen:
                        raise Exception("Syntax error: extra closing parenthesis.")
                    break
                elif sym == '(':
                    thisNode,i = self.__parseParenTree(tokens, i, True)

                    if lastNode is None:
                        lastNode = thisNode
                    else:
                        lastNode.addChildNode(thisNode)

                else:
                    thisOp = self.op_sym_to_cls[sym]()
                    thisNode = OperatorNode(token, thisOp)

                    if lastNode is None:
                        lastNode = thisNode
                    else:
                        node = lastNode
                        while node is not None:
                            ok = False
                            if node.parent is None:
                                ok = True
                            if isinstance(node, OperatorNode):
                                if compareOperatorPriority(thisOp, node.op) > 0:
                                    ok = True
                            if ok:
                                break
                            node = node.parent
                        parentNode = node

                        if not isinstance(parentNode, OperatorNode):
                            thisNode.addChildNode(parentNode)
                            lastNode = thisNode

                        elif parentNode.is_fullfilled():
                            if parentNode.parent is None:
                                thisNode.addChildNode(node)
                                lastNode = thisNode
                            else:
                                parentNode.parent.setChildNode(
                                    parentNode.parent.childNodes.index(parentNode),
                                    thisNode)
                                thisNode.addChildNode(node)
                                lastNode = thisNode
                        else:
                            parentNode.addChildNode(thisNode)
                            lastNode = thisNode

            elif tag == 'text':
                thisNode = TextNode(token)
                if lastNode is None:
                    lastNode = thisNode
                else:
                    assert isinstance(lastNode, OperatorNode)
                    lastNode.addChildNode(thisNode)

            else:
                raise Exception("Unknown token tag: %s" % tag)

        rootNode = lastNode
        while rootNode.parent is not None:
            rootNode = lastNode.parent

        return (rootNode, i)

    def __optimizeTree(self, node):
        leafNodes = node.getLeafNodes()

        def isAndNode(node):
            return isinstance(node, OperatorNode) and isinstance(node.op, Op_And)

        def isAllAndNode(node):
            if not isAndNode(node):
                return False
            for child in node.childNodes:
                if not (isinstance(child, TextNode) or isAllAndNode(child)):
                    return False
            return True

        def traverseTopDown(node, func, arg=None):
            cont = func(node, arg)
            if not cont:
                return
            for child in (node.childNodes or []):
                traverseTopDown(child, func, arg)

        def collectAllAndNodes(node, arg):
            if isAllAndNode(node):
                arg.append(node)
                return False
            return True

        def collectTextNodes(node, arg):
            if isinstance(node, TextNode):
                arg.append(node)
            return True

        allAndNodes = []
        traverseTopDown(node, collectAllAndNodes, arg=allAndNodes)

        # TODO: Generator priority
        priority = {}

        for n in allAndNodes:
            textNodes = []
            traverseTopDown(n, collectTextNodes, arg=textNodes)
            if len(textNodes) <= 1:
                continue
            def key(n):
                return priority.get(n.token[1][0], 0)
            textNodes = sorted(textNodes, key=key)

            n.childNodes[:] = []
            n_ = n
            for textNode in textNodes[:-2]:
                n1_ = OperatorNode(token=('op', 'and'), op=Op_And())
                n_.addChildNode(textNode)
                n_.addChildNode(n1_)
                n_ = n1_
            n_.addChildNode(textNodes[-2])
            n_.addChildNode(textNodes[-1])


        return node

    def get(self):
        pass
