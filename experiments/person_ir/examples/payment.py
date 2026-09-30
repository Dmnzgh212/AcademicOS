"""Purchase request; this IR does not revalidate prices or impose amount limits."""

from experiments.person_ir import Graph, Interpreter, Node, Observation


def program(merchant: str) -> Graph:
    return Graph((
        Node("order", "source", config={"name": "order", "label": "protected"}),
        Node("price", "source", config={"name": "price", "label": "protected"}),
        Node("purchase", "join", ("order", "price")),
        Node("disclose", "declassify", ("purchase",),
             {"destination": merchant, "purpose": "purchase"}),
        Node("pay", "effect_request", ("disclose",),
             {"kind": "payment", "destination": merchant}),
    ))


def request(merchant: str, observed_price: int, *, intent_id: str = "buy:1"):
    return Interpreter().run(program(merchant), {
        "order": Observation({"item": "textbook"}, "cart:1", "protected"),
        "price": Observation({"CAD": observed_price}, "quote:1", "protected"),
    }, base_version=0, producer="payment-example@1", intent_id=intent_id).effects[0]
