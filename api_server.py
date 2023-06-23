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
        elif node.class_type == "Switch (API)":
            path = node.get_input("path")
            if isinstance(path, str):
                value = read_at_position(body, path)
            else:
                print("Error: path is not a string:", path)
                value = None

            if value is None:
                value = node.get_input("switch")
            if value:
                graph.replace_node_output(id, 0, node.get_input("on_true"))
            else:
                graph.replace_node_output(id, 0, node.get_input("on_false"))
        elif node.class_type == "Value Switch (API)":
            path = node.get_input("path")
            if isinstance(path, str):
                value = read_at_position(body, path)
            else:
                print("Error: path is not a string:", path)
                value = None

            is_equal = False
            try:
                if isinstance(value, int):
                    is_equal = value == int(node.get_input("value_string"))
                elif isinstance(value, float):
                    is_equal = value == float(node.get_input("value_string"))
                else:
                    is_equal = str(value) == node.get_input("value_string")
            except:
                pass
            if is_equal:
                graph.replace_node_output(id, 0, node.get_input("on_equal"))
            else:
                graph.replace_node_output(id, 0, node.get_input("on_not_equal"))
        elif node.class_type == "Random Seed (API)":
            node.set_input("seed", random.randint(0, 0xffffffffffffffff))
    return graph

def query_to_dict(query):
    d = {}
    for key, value in query.items():
        d[key] = value
    return d

def init_api_server():
    routes = PromptServer.instance.routes

    # @routes.get('/api/{endpoint_name}')
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

    # @routes.get('/sdapi/v1/{endpoint_name}')
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

    async def api_getprompt(endpoint_name, endpoints_path, body):
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

        async with aiohttp.ClientSession() as session:
            async with session.get(get_address() + '/object_info') as resp:
                node_defs = await resp.json()
            instantiated = instantiate_from_save(node_defs, graph)
            resolved = resolve_request(instantiated, body)
            prompt = { "prompt": resolved.finalize() }
            return prompt

    async def api_endpoint(endpoint_name, endpoints_path, body):
        prompt = await api_getprompt(endpoint_name, endpoints_path, body)
        async with aiohttp.ClientSession() as session:
            async with session.post(get_address() + '/prompt_sync', json=prompt) as resp:
                try:
                    response = await resp.json()
                except Exception as e:
                    print("Error:", e)
                    raise web.HTTPInternalServerError(reason=e)
                if len(response) == 1 and "RETURN_PNG" in response:
                    base64_image = response["RETURN_PNG"][0]
                    image_bytes = base64.b64decode(base64_image)
                    return web.Response(body=image_bytes, content_type="image/png")
                return web.json_response(response)

    # @routes.get('/api_prompt/{endpoint_name}')
    async def api_get_prompt(request):
        body = query_to_dict(request.rel_url.query)
        endpoints_path = os.path.join(base_path, "endpoints")
        prompt = await api_getprompt(request.match_info['endpoint_name'], endpoints_path, body)
        return web.json_response(prompt)

    # @routes.get('/sdapi_prompt/{endpoint_name}')
    async def sdapi_get_prompt(request):
        body = query_to_dict(request.rel_url.query)
        endpoints_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sdapi")
        prompt = await api_getprompt(request.match_info['endpoint_name'], endpoints_path, body)
        return web.json_response(prompt)

