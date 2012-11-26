
from jinja2 import *

def show_all_attrs(value):
    res = []
    for k in dir(value):
        res.append('%r %r\n' % (k, getattr(value, k)))
    return '\n'.join(res)

env = Environment()
env.filters['show_all_attrs'] = show_all_attrs

# using the filter
tmpl = env.from_string('''{{v|show_all_attrs}}''')
class Myobj(object):
    a = 1
    b = 2

print tmpl.render(v=Myobj())
