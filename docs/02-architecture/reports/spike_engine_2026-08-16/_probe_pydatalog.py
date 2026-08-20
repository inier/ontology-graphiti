from pyDatalog import pyDatalog

pyDatalog.clear()
pyDatalog.load("cousin(X, Z) <= parent(X, Y) & sibling(Y, Z)")
pyDatalog.load('parent("alice", "bob")')
pyDatalog.load('sibling("bob", "dave")')

a = pyDatalog.ask('cousin("alice", X)')
print("answers=", a)
print("type=", type(a))
print("attrs=", [x for x in dir(a) if not x.startswith("__")])
if a is not None:
    print("has answers attr:", hasattr(a, "answers"))
    try:
        print("a.answers =", a.answers)
    except Exception as e:
        print("a.answers err:", e)

# 递归规则
pyDatalog.clear()
pyDatalog.load("ancestor(X, Z) <= parent(X, Y) & ancestor(Y, Z)")
pyDatalog.load("ancestor(X, Y) <= parent(X, Y)")
pyDatalog.load('parent("a", "b")')
pyDatalog.load('parent("b", "c")')
b = pyDatalog.ask('ancestor("a", X)')
print("rec answers=", b)
if b is not None:
    print("rec a.answers=", b.answers)
