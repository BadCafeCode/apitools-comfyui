from server import PromptServer
from .builder import GraphBuilder
import aiohttp
from aiohttp import web
import os
import base64
from folder_paths import base_path
import json
import re
import random
import uuid

def base64_encode_image(image_path):
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read())
    return encoded_string.decode('utf-8')

def get_input_link(node, input_name):
    inputs = node.get("inputs")
    if inputs is None:
        return True, None
    for input in inputs:
        if input["name"] == input_name:
            return "widget" in input, input["link"]
    return True, None

def merge_dict_recursive(dict1, dict2):
    """
    Recursively merges two dictionaries, concatenating arrays instead of overwriting them.
    """
    for key in dict2:
        if key in dict1:
            if isinstance(dict1[key], dict) and isinstance(dict2[key], dict):
                merge_dict_recursive(dict1[key], dict2[key])
            elif isinstance(dict1[key], list) and isinstance(dict2[key], list):
                dict1[key].extend(dict2[key])
            else:
                dict1[key] = dict2[key]
        else:
            dict1[key] = dict2[key]
    return dict1

def instantiate_from_save(node_defs, graph):
    g = GraphBuilder()
    cached_inputs = {}
    cached_nodes = {}
    for node in graph["nodes"]:
        node_type = node["type"]
        if node_type == "Note":
            continue
        id = str(node["id"])
        cached_nodes[id] = node
        n = g.node(node_type, id=id)
        if node_type == "Reroute" or node_type == "PrimitiveNode":
            cached_inputs[id] = [""]
        else:
            node_def = node_defs[node["type"]]
            cached_inputs[id] = node_def["input_order"].get("required", []) + node_def["input_order"].get("optional", [])
        widget_index = 0
        for input in cached_inputs[id]:
            has_widget, link = get_input_link(node, input)
            if has_widget:
                widgets_values = node.get("widgets_values")
                if widgets_values is not None:
                    if widget_index < len(widgets_values):
                        value = widgets_values[widget_index]
                        n.set_input(input, value)
                    widget_index += 1
                    if input == "seed": # Special case
                        widget_index += 1
        # if widget_index != 0 and widget_index != len(widgets_values):
            # print("Wrong number of widget values for node", node["id"])
            # print("All inputs:", cached_inputs[id])
            # print("Widgets values:", widgets_values)
            # print("Node inputs:", node.get("inputs"))
    for link in graph["links"]:
        [link_id, from_id, from_index, to_id, to_index, kind] = link
        from_id = str(from_id)
        to_id = str(to_id)
        from_node = g.lookup_node(from_id)
        to_node = g.lookup_node(to_id)
        to_node.set_input(cached_nodes[to_id]["inputs"][to_index]["name"], from_node.out(from_index))

    to_remove = []
    for node in g.nodes.values():
        if node.class_type == "Reroute" or node.class_type == "PrimitiveNode":
            g.replace_node_output(node.id, 0, node.get_input(""))
            to_remove.append(node.id)
        elif node.class_type == "PreviewImage":
            to_remove.append(node.id)

    for id in to_remove:
        g.remove_node(id)

    return g

def read_at_position(obj, path):
    try:
        path = re.split('[\.\[]', path)
        current = obj
        for i in range(len(path)):
            if path[i][-1] == "]":
                assert isinstance(current, list)
                key = int(path[i][:-1])
                current = current[key]
            else:
                current = current[path[i]]
        return current
    except:
        return None

def resolve_request(graph, body):
    for id, node in graph.nodes.items():
        if node.class_type == "Input (API)":
            path = node.get_input("path")
            if isinstance(path, str):
                value = read_at_position(body, path)
                if value is not None:
                    node.set_input("api_value", value)
                    node.set_input("default_input", None)
                    node.set_input("default_string", None)
            else:
                print("Error: path is not a string:", path)
        elif node.class_type == "Random Seed Input (API)":
            path = node.get_input("path")
            seed = -1
            if isinstance(path, str):
                value = read_at_position(body, path)
                if value is not None:
                    seed = int(value)
            if seed == -1:
                seed = random.randint(0, 0xffffffffffffffff)
            node.set_input("seed", seed)
    return graph

def query_to_dict(query):
    d = {}
    for key, value in query.items():
        d[key] = value
    return d

cached_objects = None
def init_api_server():
    routes = PromptServer.instance.routes

    @routes.get('/api_endpoints')
    async def api_endpoints(request):
        endpoints_path = os.path.join(base_path, "endpoints")
        files = [f for f in os.listdir(endpoints_path) if os.path.isfile(os.path.join(endpoints_path, f)) and f.endswith(".json")]
        files = [os.path.splitext(f)[0] for f in files]
        return web.json_response(files)

    def get_best_type(t1, t2):
        if t1 is None:
            return t2
        if t2 is None:
            return t1
        if t1 == "*":
            return t2
        return t1

    def get_node_output_type(graph, node_id, output_id, node_defs, cached = {}):
        cached_value = cached.get((node_id, output_id), None)
        if cached_value is not None:
            return cached_value
        cached[(node_id,output_id)] = True

        result = None
        node = graph.nodes[node_id]
        t = node.class_type
        if t == "Input (API)":
            kind = node.get_input("kind")
            if kind == "string":
                result = "STRING"
            elif kind == "integer":
                result = "INT"
            elif kind == "float":
                result = "FLOAT"
            elif kind == "boolean":
                result = "BOOLEAN"
            elif kind == "image":
                result = "IMAGE"
        else:
            node_def = node_defs[t]
            result = node_def["output"][output_id]

        cached[(node_id,output_id)] = result
        return result


    def get_node_input_type(graph, node_id, input_id, node_defs, cached = {}):
        cached_value = cached.get((node_id, input_id), None)
        if cached_value is not None:
            return cached_value
        cached[(node_id,input_id)] = True

        result = None
        node = graph.nodes[node_id]
        input_value = node.get_input(input_id)
        if input_value is None:
            result =  None
        elif isinstance(input_value, list):
            result = get_node_output_type(graph, input_value[0], input_value[1], node_defs, cached)
        elif input_id in node_defs[node.class_type]["input"].get("required", []):
            result = node_defs[node.class_type]["input"]["required"][input_id][0]
        elif input_id in node_defs[node.class_type]["input"].get("optional", []):
            result = node_defs[node.class_type]["input"]["optional"][input_id][0]
        elif isinstance(input_value, str):
            result = "STRING"
        elif isinstance(input_value, int) or isinstance(input_value, float):
            result = "FLOAT"
        else:
            result = None

        cached[(node_id,input_id)] = result
        return result

    def string_to_kind(string, kind):
        if kind == "STRING":
            return string
        elif kind == "INT":
            return int(string)
        elif kind == "FLOAT":
            return float(string)
        elif kind == "BOOLEAN":
            return string.lower() == "true"
        else:
            return None

    @routes.get('/api_info/{endpoint_name}')
    async def api_info(request):
        endpoint_name = request.match_info['endpoint_name']
        endpoints_path = os.path.join(base_path, "endpoints")
        graph = await api_instantiate(endpoint_name, endpoints_path)
        assert graph is not None
        node_defs = await get_node_defs()

        inputs = {}
        default_values = {}
        switch_inputs = {}
        outputs = {}
        cached = {}
        for id, node in graph.nodes.items():
            if node.class_type == "Input (API)":
                path = node.get_input("path")
                default_string = node.get_input("default_string")
                if isinstance(path, str):
                    inputs[path] = get_node_output_type(graph, id, 0, node_defs, cached)
                    if default_string is not None and default_string != "" and path not in default_values:
                        default = string_to_kind(default_string, inputs[path])
                        if default is not None:
                            default_values[path] = default
            elif node.class_type == "Random Seed Input (API)":
                path = node.get_input("path")
                if isinstance(path, str):
                    inputs[path] = "INT"
                    default_values[path] = node.get_input("seed")
            elif node.class_type == "Serialize (API)":
                path = node.get_input("path")
                if isinstance(path, str):
                    outputs[path] = get_node_input_type(graph, id, "value", node_defs, cached)

        for path in switch_inputs:
            if path not in inputs:
                inputs[path] = "BOOLEAN"

        return web.json_response({
            "inputs": inputs,
            "default_values": default_values,
            "outputs": outputs
        })


    @routes.get('/api/{endpoint_name}')
    async def api_endpoint_get(request):
        body = query_to_dict(request.rel_url.query)
        endpoint_name = request.match_info['endpoint_name']
        endpoints_path = os.path.join(base_path, "endpoints")
        return await api_endpoint(endpoint_name, endpoints_path, body)

    @routes.post('/api/{endpoint_name}')
    async def api_endpoint_post(request):
        body = await request.json()
        endpoint_name = request.match_info['endpoint_name']
        endpoints_path = os.path.join(base_path, "endpoints")
        return await api_endpoint(endpoint_name, endpoints_path, body)

    @routes.get('/sdapi/v1/{endpoint_name}')
    async def sdapi_endpoint_get(request):
        body = query_to_dict(request.rel_url.query)
        endpoint_name = request.match_info['endpoint_name']
        endpoints_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sdapi")
        return await api_endpoint(endpoint_name, endpoints_path, body)

    @routes.post('/sdapi/v1/{endpoint_name}')
    async def sdapi_endpoint_post(request):
        # A special case -- attempted compatibility with the automatic1111 API
        body = await request.json()
        endpoint_name = request.match_info['endpoint_name']
        endpoints_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sdapi")
        return await api_endpoint(endpoint_name, endpoints_path, body)

    def get_address():
        address = PromptServer.instance.address
        port = PromptServer.instance.port
        if address == "0.0.0.0":
            address = "127.0.0.1"
        return "http://" + address + ":" + str(port)

    def get_ws_address():
        address = PromptServer.instance.address
        port = PromptServer.instance.port
        if address == "0.0.0.0":
            address = "127.0.0.1"
        return "ws://" + address + ":" + str(port)

    async def api_getprompt(endpoint_name, endpoints_path, body):
        instantiated = await api_instantiate(endpoint_name, endpoints_path)
        resolved = resolve_request(instantiated, body)
        prompt = { "prompt": resolved.finalize() }
        return prompt

    async def get_node_defs():
        global cached_objects
        if cached_objects is None:
            async with aiohttp.ClientSession() as session:
                async with session.get(get_address() + '/object_info') as resp:
                    cached_objects = await resp.json()
        return cached_objects

    async def api_instantiate(endpoint_name, endpoints_path):
        endpoint_path = os.path.join(endpoints_path, endpoint_name + ".json")
        if not os.path.exists(endpoint_path) or endpoints_path != os.path.commonpath([endpoints_path, endpoint_path]):
            raise web.HTTPNotFound(reason="No such endpoint available.")

        # Read the file specified by endpoint_name
        try:
            with open(endpoint_path, "r") as f:
                endpoint_json = f.read()
                graph = json.loads(endpoint_json)
        except:
            raise web.HTTPNotFound(reason="Could not load endpoint.")

        node_defs = await get_node_defs()

        instantiated = instantiate_from_save(node_defs, graph)
        return instantiated

    async def api_endpoint(endpoint_name, endpoints_path, body):
        prompt = await api_getprompt(endpoint_name, endpoints_path, body)
        client_id = str(uuid.uuid4())
        prompt["client_id"] = client_id
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect("{}/ws?clientId={}".format(get_ws_address(), client_id)) as ws:
                async with session.post(get_address() + '/prompt', json=prompt) as resp:
                    try:
                        response = await resp.json()
                        prompt_id = response["prompt_id"]
                    except Exception as e:
                        print("Error:", e)
                        raise web.HTTPInternalServerError(reason=e)
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        message = msg.json()
                        if message["type"] == "executing":
                            data = message["data"]
                            if data["node"] is None and data["prompt_id"] == prompt_id:
                                break
                async with session.get(get_address() + '/history/' + prompt_id) as resp:
                    response = await resp.json()
                    result = {}
                    ui_outputs = response[prompt_id]["outputs"]
                    for node_id in ui_outputs:
                        if "api_output" in ui_outputs[node_id]:
                            for x in ui_outputs[node_id]["api_output"]:
                                result = merge_dict_recursive(result, x)
                    if len(result) == 1 and "RETURN_PNG" in result:
                        base64_image = result["RETURN_PNG"][0]
                        image_bytes = base64.b64decode(base64_image)
                        return web.Response(body=image_bytes, content_type="image/png")
                    return web.json_response(result)

    @routes.get('/api_prompt/{endpoint_name}')
    async def api_get_prompt(request):
        body = query_to_dict(request.rel_url.query)
        endpoints_path = os.path.join(base_path, "endpoints")
        prompt = await api_getprompt(request.match_info['endpoint_name'], endpoints_path, body)
        return web.json_response(prompt)

    @routes.get('/sdapi_prompt/{endpoint_name}')
    async def sdapi_get_prompt(request):
        body = query_to_dict(request.rel_url.query)
        endpoints_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sdapi")
        prompt = await api_getprompt(request.match_info['endpoint_name'], endpoints_path, body)
        return web.json_response(prompt)

