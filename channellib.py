from websockets import ClientConnection as Conn
import json

async def intro(name, desc, ws, tool=False):
    await ws.send(json.dumps({
            "name": name,
            "description": desc,
            "tool": tool
        }))
    
async def simple_send_msg(msg, ws, wake=None, notif_message=None, priority=None):
    payload = {
        "message": msg
    }
    wt = None
    if wake:
        payload["wake"] = True
        if wake != True:
            payload["wake_message"] = wake
    if notif_message is not None:
        payload["notif_message"] = notif_message
    if priority is not None:
        payload["priority"] = priority

    await ws.send(json.dumps(payload))

