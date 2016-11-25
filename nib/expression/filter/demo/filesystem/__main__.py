import sys
import re

from nib.expression.filter import parser, environment
from .generators import get_generator_classes


class EvaluationEnvironment(environment.EvaluationEnvironment):
    def get_generators(self):
        return [cls() for cls in get_generator_classes()]


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
