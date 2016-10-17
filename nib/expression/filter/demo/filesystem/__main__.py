import sys
import re

from nib.expression.filter import parser, environment
from .generators import get_generator_classes


class EvaluationEnvironment(environment.EvaluationEnvironment):
    def __init__(self):
        generatorClss = get_generator_classes()

        self.generators = {}
        for cls in generatorClss:
            self.generators[cls.key] = cls()

        return

    def evalGenerator(self, expr, input, positive):
        key,qt = expr

        m = re.match(r'([-a-z0-9]+)(?:\[(.*)\]|)', key)
        key = m.group(1)
        optstr = m.group(2) or ''

        opts = {}
        for s in optstr.split(','):
            f = s.split('=', 1)
            if len(f) == 1:
                opts[f[0]] = True
            else:
                opts[f[0]] = f[1]

        if key in self.generators:
            generator = self.generators[key]
        else:
            raise Exception("Invalid generator: %s" % key)

        return generator.eval(input, qt, opts, positive)



def run_demo():
    args = sys.argv[1:]
    if len(args) > 0:
        queries = args
    else:
        # Some toy examples
        queries = [
            # Find large log files
            "path:/var/log and size:1048576-",

            # Find configuration files somewhat related to keyboard
            "path:/etc and regex:.*keyboard.*",

            # Find non-symlink files in /etc/alternatives
            "path:/etc/alternatives and not symlink",

            # Dereference symlinks in /etc/alternatives and shows only items
            # whose dereferenced path is in /usr/bin
            "path:/etc/alternatives and recurse and realpath and path:/usr/bin",

            # Find configuration files whose size is some specific values
            "path:/etc and ( size:1024 or size:2048 or size:3072 )",
        ]

    for query in queries:
        msg = "Query: {}".format(query)
        print("=" * (len(msg)+1))
        print(msg)
        print("=" * (len(msg)+1))

        expr_tree = parser.QueryParser(query).getTree()
        env = EvaluationEnvironment()

        for item in expr_tree.eval(env):
            print(item.get_path())

        print()


if __name__ == '__main__':
    run_demo()
