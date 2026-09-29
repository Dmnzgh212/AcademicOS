"""Structural verifier for the deliberately small, data-only slice 1 IR."""

from .model import Graph, Node


class VerificationError(ValueError):
    pass


def verify(graph: Graph) -> None:
    if not isinstance(graph, Graph) or not isinstance(graph.nodes, tuple):
        raise VerificationError("graph must contain a tuple of nodes")
    kinds = {}
    labels = {}
    graph_node_config = {}
    arity = {"source": 0, "select": 1, "join": 2, "derive": 1,
             "propose": 1, "commit_request": 1, "declassify": 1,
             "effect_request": 1, "output": 1}
    config_keys = {
        "source": {"name", "label"}, "select": {"key"}, "join": set(),
        "derive": set(), "propose": {"target"}, "commit_request": set(),
        "declassify": {"destination", "purpose"},
        "effect_request": {"kind", "destination"}, "output": set(),
    }
    for node in graph.nodes:
        if not isinstance(node, Node):
            raise VerificationError("graph contains a non-node")
        if not isinstance(node.id, str) or not node.id or node.id in kinds:
            raise VerificationError(f"duplicate or invalid node id: {node.id!r}")
        if node.op not in arity or not isinstance(node.inputs, tuple) or len(node.inputs) != arity[node.op]:
            raise VerificationError(f"unsupported operation or arity: {node.id}")
        if not isinstance(node.config, dict) or set(node.config) != config_keys[node.op]:
            raise VerificationError(f"invalid configuration: {node.id}")
        if any(dep not in kinds for dep in node.inputs):
            raise VerificationError(f"missing or forward input: {node.id}")
        for key, value in node.config.items():
            if not isinstance(value, str) or not value.strip():
                raise VerificationError(f"invalid {key}: {node.id}")
        input_kinds = tuple(kinds[dep] for dep in node.inputs)
        data_kinds = {"source", "select", "join", "derive"}
        if node.op in {"select", "join", "derive", "propose", "declassify"} and any(k not in data_kinds for k in input_kinds):
            raise VerificationError(f"expected ordinary data: {node.id}")
        if node.op == "commit_request" and input_kinds != ("propose",):
            raise VerificationError(f"commit requires proposal: {node.id}")
        if node.op == "effect_request":
            dep = node.inputs[0]
            if input_kinds != ("declassify",) and (input_kinds[0] not in data_kinds or labels[dep] != "public"):
                raise VerificationError(f"protected effect requires disclosure request: {node.id}")
            if input_kinds == ("declassify",) and graph_node_config[dep]["destination"] != node.config["destination"]:
                raise VerificationError(f"disclosure destination mismatch: {node.id}")
        if node.op == "output" and input_kinds[0] not in data_kinds | {"propose", "commit_request", "declassify", "effect_request"}:
            raise VerificationError(f"unsupported output: {node.id}")
        if node.op == "source" and node.config["label"] not in {"public", "protected"}:
            raise VerificationError(f"invalid source label: {node.id}")
        if node.op == "source":
            label = node.config["label"]
        elif node.op in {"select", "derive"}:
            label = labels[node.inputs[0]]
        elif node.op == "join":
            label = "protected" if "protected" in (labels[dep] for dep in node.inputs) else "public"
        else:
            label = "request"
        kinds[node.id] = node.op
        labels[node.id] = label
        graph_node_config[node.id] = node.config
