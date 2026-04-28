import asyncio
import websockets
import json
import sys
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
import channellib

URI = "ws://127.0.0.1:8282"

async def send_messages(ws, session):
    while True:
        try:
            msg = await session.prompt_async("\n> ")
            await channellib.simple_send_msg(msg, ws, True, "New message via CLI", 1)
            payload = {
                "notif_message": f"New message via CLI: {msg}",
                "priority": 1,
                "wake": True,
                "message": msg
            }
            #print("Sending: ", payload)
            await ws.send(json.dumps(payload))
        except KeyboardInterrupt:
            payload = {
                "exit":True
            }
            #print("Sending: ", payload)
            await ws.send(json.dumps(payload))
            await ws.close()
            return


async def receive_messages(ws):
    while True:
        try:
            message = await ws.recv()
            try:
                parsed = json.loads(message)
                m = parsed.get("text")
                if m != None:
                    print(f"[Server] {m}")
                else:
                    print(f"Error: {message}")
                    await channellib.simple_send_msg('The previous message failed to parse. Reminder: this channel\'s schema is {"text":[your message]}.', ws, True, "Invalid Json on last call to shell.")
            except json.JSONDecodeError:
                print(f"[Server Raw] {message}")
        except websockets.ConnectionClosed:
            print("Connection closed.")
            await ws.close()
            return


async def main():
    session = PromptSession()

    async with websockets.connect(URI) as ws:
        await channellib.intro("CLI chat", 'CLI based chat interface.\nTo send a message, send a JSON object with the key "text", it\'s value being the text you want to send.', ws)
        print("[Chat] ready")
        with patch_stdout():
            await asyncio.gather(
                receive_messages(ws),
                send_messages(ws, session)
            )
            print("Out")

def run_chat():
    asyncio.run(main())

if __name__ == "__main__":
    run_chat()