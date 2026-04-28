import asyncio
import websockets
import json
import subprocess


URI = "ws://127.0.0.1:8282"


async def simple_send_msg(msg, ws, wake=None, notif_message=None, priority=None):
    payload = {
        "message": msg
    }
    if wake is not None:
        payload["wake"] = wake
    if notif_message is not None:
        payload["notif_message"] = notif_message
    if priority is not None:
        payload["priority"] = priority

    await ws.send(json.dumps(payload))


def run_command(cmd: str):
    print(cmd)
    """Execute shell command and return output + exit code."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            text=True,
            capture_output=True
        )
        output = None
        if (len(result.stdout) + len(result.stderr)) != 0:
            output = ("stdout:\n"+result.stdout + "\nstderr:\n" + result.stderr).strip()
        else:
            output = "(No output was returned)"

        return {
            "output": output,
            "exit_code": result.returncode
        }

    except Exception as e:
        return {
            "output": f"error: {e}",
            "exit_code": 1
        }


async def handle_server(ws):
    """Receive commands from server and execute them."""
    while True:
        try:
            msg = await ws.recv()

            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                simple_send_msg("Invalid json!", ws, notif_message="Previous command encountered an error.", wake="Previous command encountered an error.")

            cmd = data.get("command")
            if cmd == None:
                await simple_send_msg("Invalid message, usage: {\"command\":\"command_name --example_arg\"}", ws, notif_message="There was an issue with your last message to shell channel.", wake="There was an issue with your last command.")
            print(f"\n[exec] running \"{cmd}\"")
            result = run_command(cmd)
            response_text = json.dumps({
                "command": cmd,
                "output": result["output"],
                "exit_code": result["exit_code"]
            })
            print(f"\n[exec] \"{cmd}\" done. ({result["exit_code"]})\n[exec]{result["output"].split("\n")}")
            await simple_send_msg(
                response_text,
                ws,
                notif_message=f"Command executed: {cmd}",
                priority=1,
                wake="The command you ran has finished."
            )

        except websockets.ConnectionClosed:
            print("Connection closed.")
            break


async def main():
    async with websockets.connect(URI) as ws:
        # register
        await ws.send(
            json.dumps({
                "name": "Shell",
                "description": "Channel for shell calls. Run using json of shape  {\"command\":\"command_name --example_arg\"}",
                "tool":True
            })
        )

        print("[exec] ready")

        await handle_server(ws)


def start():
    asyncio.run(main())
