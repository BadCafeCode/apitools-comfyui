import json

def example_usage():
    graph = GraphBuilder()
    loader = graph.node("LoadImage", image="image.jpg")
    serializer = graph.node("Serialize (API)", path="results[].image", image_value = loader.out(0))
    serializer2 = graph.node("Serialize (API)", path="results[-1].seed", json_object_optional=serializer.out(0), int_value=5)
    output = graph.finalize()
    expected_output = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {
                "image": "image.jpg"
            }
        },
        "2": {
            "class_type": "Serialize (API)",
            "inputs": {
                "path": "results[].image",
                "image_value": ["1", 0],
            }
        },
        "3": {
            "class_type": "Serialize (API)",
            "inputs": {
                "path": "results[-1].seed",
                "json_object_optional": ["2", 0],
                "int_value": 5
            }
        }
    }

class GraphBuilder:
    def __init__(self):
        self.nodes = {}
        self.id_gen = 1

    def node(self, class_type, id=None, **kwargs):
        if id is None:
            id = str(self.id_gen)
            self.id_gen += 1
        if id in self.nodes:
            return self.nodes[id]

        node = Node(id, class_type, kwargs)
        self.nodes[id] = node
        return node

    def lookup_node(self, id):
        return self.nodes.get(id)

    def finalize(self):
        output = {}
        for node_id, node in self.nodes.items():
            output[node_id] = node.serialize()
        return output

    def replace_node_output(self, node_id, index, new_value):
        to_remove = []
        for node in self.nodes.values():
            for key, value in node.inputs.items():
                if isinstance(value, list) and value[0] == node_id and value[1] == index:
                    if new_value is None:
                        to_remove.append((node, key))
                    else:
                        node.inputs[key] = new_value
        for node, key in to_remove:
            del node.inputs[key]

    def remove_node(self, id):
        del self.nodes[id]

class Node:
    def __init__(self, id, class_type, inputs):
        self.id = id
        self.class_type = class_type
        self.inputs = inputs

    def out(self, index):
        return [self.id, index]

    def set_input(self, key, value):
        if value is None:
            if key in self.inputs:
                del self.inputs[key]
        else:
            self.inputs[key] = value

    def get_input(self, key):
        return self.inputs.get(key)

    def serialize(self):
        return {
            "class_type": self.class_type,
            "inputs": self.inputs
        }
