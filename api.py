import json
import re
import subprocess
import sys
import copy
import io
import numpy as np
import torch
import base64
import random
from PIL import Image

# Eww. I'm sure there's a better way to do this, but it's probably not worth the effort
def store_at_position(obj, result, path):
    path = re.split('[\.\[]', path)
    current = obj
    for i in range(len(path) - 1):
        next_is_list = path[i + 1][-1] == "]"
        if path[i] == "]":
            assert isinstance(current, list)
            if next_is_list:
                current.append([])
            else:
                current.append({})
            current = current[-1]
        elif path[i][-1] == "]":
            assert isinstance(current, list)
            key = int(path[i][:-1])
            if key == -1 and len(current) == 0:
                key = 0
            if key >= len(current):
                current += [None] * (key - len(current) + 1)
            if current[key] is None:
                if next_is_list:
                    current[key] = []
                else:
                    current[key] = {}
            current = current[key]
        elif path[i] not in current:
            key = path[i]
            if next_is_list:
                current[key] = []
            else:
                current[key] = {}
            current = current[key]
        else:
            current = current[path[i]]

    last = path[-1]
    if last == "]":
        current.append(result)
    elif last[-1] == "]":
        key = int(last[:-1])
        if key >= len(current):
            current += [None] * (key - len(current) + 1)
        current[key] = result
    else:
        current[last] = result


def serialize_image(images):
    B, H, W, C = images.shape
    results = []
    for b in range(B):
        image = images[b] * 255
        array = image.cpu().numpy()
        im = Image.fromarray(np.uint8(array))
        im.convert('RGBA')
        f = io.BytesIO()
        im.save(f, format='PNG')
        results.append(base64.b64encode(f.getvalue()).decode("utf-8"))
    return results

def default_serialize(value):
    return value

def GenericSerializeNodeFactory(name, arg_type, serialize_function=default_serialize, default_value=None):
    class GenericSerializeNode:
        def __init__(self):
            pass

        @classmethod
        def INPUT_TYPES(cls):
            if default_value is None:
                value = (arg_type,)
            else:
                value = (arg_type, {"default": default_value})
            return {
                "required": {
                    "value": value,
                    "path": ("STRING", {"multiline": False}),
                },
                "optional": {
                    "json_object_optional": ("JSON_OBJECT",)
                },
            }

        FUNCTION = "output"
        RETURN_TYPES = ("JSON_OBJECT",)

        CATEGORY = "API Output"

        def output(self, value, path, json_object_optional=None):
            output = serialize_function(value)
            if json_object_optional is None:
                return ([(path, output)],)
            else:
                # return (copy.deepcopy(json_object_optional) + [(path, output)],)
                return (json_object_optional + [(path, output)],)

    GenericSerializeNode.__name__ = name
    return GenericSerializeNode

class APISerializeNode:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "path": ("STRING", {"multiline": False}),
                "value": ("*",),
            },
            "optional": {
                "json_object_optional": ("JSON_OBJECT",),
            },
        }

    FUNCTION = "output"
    RETURN_TYPES = ("JSON_OBJECT",)

    CATEGORY = "API Output"

    def output(self, path, value, json_object_optional=None):
        if isinstance(value, torch.Tensor):
            value = serialize_image(value)

        if json_object_optional is None:
            return ([(path, value)],)
        else:
            # return (copy.deepcopy(json_object_optional) + [(path, output)],)
            return (json_object_optional + [(path, value)],)

def deserialize_image(image_input):
    if not isinstance(image_input, list):
        image_input = [image_input]

    result = None
    for image_string in image_input:
        decoded = base64.b64decode(image_string)
        image = Image.open(io.BytesIO(decoded)).convert('RGB')
        # image.save("/home/guill/Desktop/test_result.png", format="PNG")
        image_array = np.array(image).astype(np.float32)
        tensor = torch.from_numpy(image_array / 255.0)
        tensor = tensor.unsqueeze(0)
        if result is None:
            result = tensor
        else:
            result = torch.cat([result, tensor], dim=0)
    return result

def default_deserialize(value):
    return value

def GenericInputNodeFactory(name, arg_type, deserialize_function=default_deserialize, default_value=None):
    class GenericInputNode:
        def __init__(self):
            pass

        @classmethod
        def INPUT_TYPES(cls):
            if default_value is None:
                value = (arg_type,)
            else:
                value = (arg_type, {"default": default_value})
            return {
                "required": {
                    "path": ("STRING", {"multiline": False}),
                },
                "optional": {
                    "default_value": value,
                },
                "hidden": {
                    "api_value": value,
                },
            }

        FUNCTION = "input"
        RETURN_TYPES = (arg_type,)

        CATEGORY = "API Input"

        def input(self, path, default_value = None, api_value = None):
            if api_value is not None:
                return (deserialize_function(api_value),)
            elif default_value is not None:
                return (default_value,)
            else:
                return (None,)

    GenericInputNode.__name__ = name
    return GenericInputNode

class SerializeImageNode:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "path": ("STRING", {"multiline": False}),
            },
            "optional": {
                "json_object_optional": ("JSON_OBJECT",)
            },
        }

    FUNCTION = "output"
    RETURN_TYPES = ("JSON_OBJECT",)

    CATEGORY = "API Output"

    def output(self, image, path, json_object_optional=None):
        output = "The image goes here"
        if json_object_optional is None:
            return ([(path, output)],)
        else:
            # return (copy.deepcopy(json_object_optional) + [(path, output)],)
            return (json_object_optional + [(path, output)],)

class APIOutputNode:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "json_object": ("JSON_OBJECT",),
            },
            "optional": {
                "extra_object2": ("JSON_OBJECT",),
                "extra_object3": ("JSON_OBJECT",),
                "extra_object4": ("JSON_OBJECT",),
                "extra_object5": ("JSON_OBJECT",),
            },
        }

    FUNCTION = "output"
    RETURN_TYPES = ()
    OUTPUT_NODE = True

    CATEGORY = "API Output"

    def output(self, json_object, extra_object2=None, extra_object3=None, extra_object4=None, extra_object5=None):
        obj = json_object
        if extra_object2 is not None:
            obj = obj + extra_object2
        if extra_object3 is not None:
            obj = obj + extra_object3
        if extra_object4 is not None:
            obj = obj + extra_object4
        if extra_object5 is not None:
            obj = obj + extra_object5

        output = {}
        for i in range(len(obj)):
            path, value = obj[i]
            store_at_position(output, copy.deepcopy(value), path)

        return { "ui": { "api_output": [output] } }

class APIInputNode:
    def __init__(self):
        pass
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "path": ("STRING", {"multiline": False}),
                "kind": (["string", "integer", "float", "boolean", "image"],),
            },
            "optional": {
                "default_string": ("STRING", {"multiline": False}),
                "default_input": ("*",),
            },
            "hidden": {
                "api_value": ("*",),
            },
        }

    FUNCTION = "input"
    RETURN_TYPES = ("*",)

    CATEGORY = "API Input"

    def input(self, path, kind, default_string = None, default_input = None, api_value = None):
        value = api_value
        if value is None:
            value = default_input
        if value is None:
            if default_string != "" or kind == "string" :
                value = default_string

        if kind == "string":
            value = str(value)
        elif kind == "integer":
            value = int(value)
        elif kind == "float":
            value = float(value)
        elif kind == "boolean":
            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            else:
                try:
                    value = bool(int(value))
                except:
                    value = False
        elif kind == "image":
            if not isinstance(value, torch.Tensor):
                value = deserialize_image(value)

        return (value,)

class APIRandomSeedInput:
    def __init__(self):
        pass
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": ("INT", {"default": -1, "min": -1, "max": 0xffffffffffffffff}),
                "path": ("STRING", {"multiline": False}),
            }
        }

    FUNCTION = "random_seed"
    RETURN_TYPES = ("INT",)

    CATEGORY = "API Input"

    def random_seed(self, seed, path):
        if seed is None or seed == -1:
            seed = random.randint(0, 0xffffffffffffffff)
        return (seed,)

class MergeJSONObjectsNode:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "json_object1": ("JSON_OBJECT",),
            },
            "optional": {
                "extra_object2": ("JSON_OBJECT",),
                "extra_object3": ("JSON_OBJECT",),
                "extra_object4": ("JSON_OBJECT",),
                "extra_object5": ("JSON_OBJECT",),
            },
        }

    FUNCTION = "merge"
    RETURN_TYPES = ("JSON_OBJECT",)

    CATEGORY = "API Output"

    def merge(self, json_object, extra_object2=None, extra_object3=None, extra_object4=None, extra_object5=None):
        obj = json_object
        if extra_object2 is not None:
            obj = obj + extra_object2
        if extra_object3 is not None:
            obj = obj + extra_object3
        if extra_object4 is not None:
            obj = obj + extra_object4
        if extra_object5 is not None:
            obj = obj + extra_object5

        return (obj,)

NODE_CLASS_MAPPINGS = {
    "API Output": APIOutputNode,
    # "Serialize Image (API)": SerializeImageNode,
    # "Image Output (API)": GenericSerializeNodeFactory("Image Output (API)", "IMAGE", serialize_function=serialize_image),
    # "Integer Output (API)": GenericSerializeNodeFactory("Integer Output (API)", "INT", default_value=0),
    # "Float Output (API)": GenericSerializeNodeFactory("Float Output (API)", "FLOAT", default_value=0.0),
    # "Text Output (API)": GenericSerializeNodeFactory("String Output (API)", "STRING", default_value=""),
    "Serialize (API)": APISerializeNode,
    "Merge JSON Objects": MergeJSONObjectsNode,

    "Input (API)": APIInputNode,
    # "Image Input (API)": GenericInputNodeFactory("Image Input (API)", "IMAGE", deserialize_function=deserialize_image),
    # "Integer Input (API)": GenericInputNodeFactory("Integer Input (API)", "INT", default_value=0),
    # "Float Input (API)": GenericInputNodeFactory("Float Input (API)", "FLOAT", default_value=0.0),
    # "Text Input (API)": GenericInputNodeFactory("String Input (API)", "STRING", default_value=""),

    "Random Seed Input (API)": APIRandomSeedInput,

}
