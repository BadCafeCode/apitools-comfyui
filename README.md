# apitools-comfyui
Note - This node pack requires a PR that has not yet been merged into the main ComfyUI Repo.

This node pack allows you to use the default ComfyUI editor to prototype and implement synchronous and easy-to-use HTTP endpoints. This is useful for integrating ComfyUI workflows into other systems -- particularly non-interactive ones.

## Included Endpoints
This node pack includes two endpoints that allow ComfyUI to act as a swap-in replacement for the Automatic1111 API when using many tools.
* `/sdapi/v1/txt2img` - A mostly-compatible implementation of Automatic1111's API of the same path.
* `/sdapi/v1/img2img` - A mostly-compatible implementation of Automatic1111's API of the same path.

Both of these endpoints support ControlNets (via the `alwayson_scripts` setting) and the txt2img one supports hr_fix.

Both of these endpoints require that a recent version of [Masquerade Nodes](https://github.com/BadCafeCode/masquerade-nodes-comfyui) be installed.

## Custom Endpoints
To create additional endpoints, simply save standard workflow .json files in the `endpoints` directory within the ComfyUI folder (where the `outputs` folder is located). Those endpoints can then be accessed via a POST request to `/api/{endpoint_name}`.

For example, if you save a workflow as `endpoints/my_endpoint.json`, you can execute it via a POST request to `localhost:8188/api/my_endpoint`.

## Concepts
### Input
#### `Input (API)`
This node is the primary way to get input for your workflow.
* `path` - A simplified JSON path to the value to get. For example, `alwayson_scripts.controlnet.args[0].model`. See the paths section below for more details. Note that `path` MUST be a string literal and cannot be processed as input from another node.
* `kind` - What type to expect for this value -- e.g. `image`, `string`, `integer`, etc. Note that images are expected to be encoded as base64 strings.
* `default_input` - If the path does not exist in the request (or you're running in the default UI rather than using an HTTP endpoint)
* `default_string` - An alternative way to specify the default value. Rather than using a second node, you can specify the default value directly in the node as a string.

![InputExample](https://github.com/BadCafeCode/apitools-comfyui/assets/3157454/612b3185-2738-474d-a2ec-453ef25bbda7)

#### `Switch (API)`
This node allows entire sections of the graph to be excluded based on the existence (or lack) of certain arguments. For example, the HighResFix part of the txt2img graph will be skipped if `hr_fix` is not set to true.
* `path` - A simplified JSON path to the value to check. For example, `hr_fix`. See the paths section below for more details. Note that `path` MUST be a string literal and cannot be processed as input from another node.
* `on_false` - The value that will be used by the switch if the path does not exist or is falsey.
* `on_true` - The value that will be used by the switch if the path exists and is truthy.
* `test_switch` - This controls which path is used when running via the default UI (for development purposes) rather than via an actual HTTP endpoint. Note that in the default UI, both input nodes will need to be evaluated even though only one of them will be used. (ComfyUI doesn't currently have support for lazy evaluation.)

![SwitchExample](https://github.com/BadCafeCode/apitools-comfyui/assets/3157454/a849c7c7-33a8-4cb0-aaa8-6282049b768b)

#### `Value Switch (API)`
This node works the same was as the Switch, but compares equality to a particular value rather than simply checking whether the value is true or false.
* `path` - A simplified JSON path to the value to check. For example, `hr_fix`. See the paths section below for more details. Note that `path` MUST be a string literal and cannot be processed as input from another node.
* `value_string` - The value to compare against. Note that this MUST be a string literal and cannot be processed as input from another node.
* `on_not_equal` - The value that will be used by the switch if the path does not exist or is not equal to the specified value.
* `on_equal` - The value that will be used by the switch if the path exists and is equal to the specified value.
* `test_value` - This controls which path is used when running via the default UI (for development purposes) rather than via an actual HTTP endpoint. Note that in the default UI, both input nodes will need to be evaluated even though only one of them will be used. (ComfyUI doesn't currently have support for lazy evaluation.)

![ValueSwitchExample](https://github.com/BadCafeCode/apitools-comfyui/assets/3157454/1176c9a2-6a6a-48fd-8902-be9329eb544f)

#### `Random Seed (API)`
This node is used to generate random numbers during endpoint execution. The special node is necessary due to technical reasons (specifically the fact that the back-end doesn't know or care about the `control_after_generation` inputs to nodes).

### Output
#### `Serialize (API)`
This node is used to return values or images to the requester.
* `path` - A simplified JSON path to the value to return. For example, `face_masks[].rect`. See the paths section below for more details.
* `value` - The value to serialize.
* `json_object_optional` - This input can be used to insert values into an existing JSON object. For example, an image could be inserted with the path `results[].image` and then the seed associated with that image saved with `results[-1].seed`.

![OutputExample](https://github.com/BadCafeCode/apitools-comfyui/assets/3157454/c7905866-dcb2-4dda-ba94-2ae6ae122091)

#### `API Output`
In order for JSON results to actually be returned to the user, they must be passed into this node. If multiple JSON objects act as inputs to this node, they will be recursively merged together (with arrays concatenating)

#### `Merge JSON Objects`
This node can be used to recursively merge JSON objects together (with arrays concatenating). It is only necessary if you have more than five objects you're trying to send to an API Output.

## Paths
Paths are parsed via a simplified parser and do not support full JSONPath syntax. The following syntax is supported:
* `parent.foo` - This will return the value of the `foo` key in the object stored in the `parent` variable.
* `parent[N]` - This will return the Nth element of the array stored in the `parent` variable. N must be a constant. Negative indices are allowed to index from the back.
* `parent[]` - For **output only**. This will append to the array stored in the `parent` variable.




