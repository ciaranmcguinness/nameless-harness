from websockets import ClientConnection as Conn
import json

async def intro(name, desc, ws, tool=False):
    await ws.send(json.dumps({
            "name": name,
            "description": desc,
            "tool": tool
        }))