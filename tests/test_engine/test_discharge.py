from puzzlespec.meta import DischargeEngine, Tactic
from puzzlespec import Int, var, U
from puzzlespec.libs import std, nd

# Goal
# B != 0
# 
# Witnesses: B \in Nat
def test1():
    t0 = U(Int).forall(lambda b: (b>0).implies(b!=0))
    Gt0_To_NE0 = Tactic.make(t0)

    B = var(std.Nat)
    goal = (B != 0)

    BDom = B.T.ref_dom
    wit0 = BDom.contains(B).simplify()

    e = DischargeEngine(Gt0_To_NE0)
    status = e.prove_backwards(goal.node, [wit0.node])
    assert status=="Proven"
#test1()

def test2():
    # all F: A->B, v: B. (E x. F(x) = v) => v \in Img[F]
    t0 = std.forall(
        [Int.to(Int.DomT), Int.DomT],
        lambda F, v: (std.exists(
            [Int],
            lambda x: F(x)==v 
            )).implies(F.image.contains(v))
    )
    print(t0)
    t0 = Tactic.make(t0)
    print(t0)

    B = var(nd.fin(5))
    img = nd.fin(5).map(lambda i: i.singleton).image
    F = nd.fin(5).map(lambda i: i.singleton)
    f2 = F(2)
    goal = img.contains(B.singleton)
    print(goal.simplify())

    BDom = B.T.ref_dom
    wit0 = BDom.contains(B)
    print(wit0.simplify())
    e = DischargeEngine(t0)
    status = e.prove_backwards(goal.node, [wit0.node])
    print(status)

test2()