from agents import Agent, Runner, function_tool, set_tracing_export_api_key, set_tracing_disabled
from websockets.sync.server import serve
from websockets.sync.server import ServerConnection
import json
import config
from threading import Lock
import time

if config.openai_tracing_key != None:
    set_tracing_export_api_key(config.openai_tracing_key)
else:
    set_tracing_disabled(True)

provider = config.provider

class AgentMain():
    def __init__(self, memory, soul):
        self.notifications = {1:[],2:[],3:[]}
        self.memory = memory
        self.tools = [self.get_clear_notif(), self.get_remember(), self.get_forget()]
        self.lock = Lock()
        self.soul = soul
        self.model = provider.get_model(config.model)

        self.channels = {}
        self.ws_server = None
        self.active_chat_channel = "CLI chat"
        self.active_tool_channel = "Shell"
        self.setup_channels()
    
    def get_clear_notif(self):
        @function_tool
        def clear_notification(priority:int, index:int =0):
            """
            Clear the notification at the specified priority and index. 
            An index of 0 deletes the oldest notification.
            Make sure to clear notifications you no longer need, as they are not automatically cleared.
            """
            if index >= len(self.notifications[priority]):
                return "Index out of range."
            else:
                x = self.notifications[priority].pop(index)
                return f"Success. Notification \"{x}\" cleared."
        return clear_notification

    def get_remember(self):
        @function_tool
        def remember(info:str):
            """
            Remember the information specified.
            Use this for anything from tasks in progress to any speedbumps you've hit.
            Also use it for personal housekeeping, such as how you're feeling and any ideas things such as improvements to your harness and channels or personal projects.
            """
            proto = self.memory + "\n" + info
            if len(info.split("\n")) > 4096:
                return "Trying to remember too much, this is likely better suited to writing in a file."
            if len(proto.split("\n")) > 4096:
                return "Memory too full, forget some stuff."
            self.memory = proto
            return "Success!"
        return remember
        
    def get_forget(self):
        @function_tool
        def forget(lines:int,start:int = 0):
            """
            Forget the specified number of lines, optionally keeping the lines specified in start.
            """
            if start+lines > len(self.memory):
                return "Trying to forget out of bounds!"
            self.memory = (self.memory[0:start] + self.memory[start+lines:])
            return "Success"
        return forget

    def get_instructions_outer(self):
        def dynamic_instructions(ctx, agent):
            m = self.memory.strip()
            if m == "":
                m = "(There is currently nothing in your memory.)"
            notifproto = ""
            for level, notifs in self.notifications.items():
                if len(notifs) != 0:
                    notifproto += f'Level {level}: "{'", "'.join(notifs)}"'
            if notifproto != "":
                notifproto = f"\nThe following are your notifications:\n{notifproto}"
            out =  f"""{self.soul}
If you ever seem to be stuck in a loop or something is completely broken, just alert the user and return.
Make sure to make liberal use of your memory, as your thinking is not preserved after you return. It is very high capacity, so make sure to lean towards over using it.
You need to use sending via channels to use your tools, all regular outputs are forwarded to the current chat channel.
Your currently selected chat channel is "{self.active_chat_channel}" and your active tool channel is "{self.active_tool_channel}". It's description is "{self.channels[self.active_tool_channel]["description"]}".
The following are the contents of your memory:
{m}{notifproto}"""
            return out
        return dynamic_instructions

    def setup_channels(self):
        def handler(conn:ServerConnection):
            info = {}
            try:
                info = json.loads(conn.recv())
            except:
                conn.close(reason="Invalid JS")
            if info.get("name") == None:
                conn.close(reason="Invalid registration")
            name = info["name"]

            self.channels[name] = {"client":conn,"messages":[],"tool":info.get("tool",False)}
            self.channels[name]["description"] = info.get("description","The channel did not provide a description.")
            while True:
                decoded = None
                try:
                    decoded = json.loads(conn.recv())
                except:
                    continue
                if decoded.get("exit", False):
                    print("exiting")
                    self.ws_server.shutdown() # type: ignore
                if (True in [decoded.get("notif_message") != None, decoded.get("wake_message") != None, decoded.get("message") != None]):
                    self.channels[name]["messages"].append({"timestamp":time.localtime(), "from":decoded.get("sender",name)})

                if decoded.get("message") != None:
                    self.channels[name]["messages"][-1]["text"] = decoded["message"]

                if decoded.get("notif_message") != None:
                    if self.channels[name]["messages"][-1].get("text") == None:
                        self.channels[name]["messages"][-1]["text"] = decoded["notif_message"]
                    self.notifications[decoded.get("priority",3)].append(decoded["notif_message"])
                    print(f"[Agent main] level {decoded.get("priority",3)} notification recived: ", decoded["notif_message"])

                if decoded.get("wake", False):
                    if self.channels[name]["messages"][-1].get("text") == None:
                        self.channels[name]["messages"][-1]["text"] = decoded["wake_message"]
                    if self.lock.acquire(False):
                        try:
                            wm = decoded.get("wake_message", self.channels[name]["messages"][-1]["text"])
                            if (self.channels[name]["tool"]) and (wm != None):
                                wm += "Note, the following is an automated message: "

                            self.run(wm)
                        finally:
                            self.lock.release()

        self.ws_server = serve(handler, host='127.0.0.1', port=8282)

        @function_tool
        def list_channels(tool:bool = False):
            """
            List all connected channels. 
            """
            proto = ""
            for k,v in self.channels.items():
                if tool == v["tool"]:
                    proto += k
                    proto += f": {v.get("description", "no description given.")}"
                    proto += "\n"
            if proto == "":
                proto = "No channels registered."
            return proto
        
        @function_tool
        def set_active_channel(name:str) -> str:
            """
            Set the active channel to the one specified by the parameter name. Changes the tool that composes your message history and works with send_message and read_messages.
            """
            if name in self.channels.keys():
                if self.channels[name]["tool"]:
                    self.active_tool_channel = name
                else:
                    self.active_chat_channel = name
                return "Success!"
            else:
                return "Unknown channel"
            
        @function_tool
        def send_message(message:str, tool:bool = False) -> str:
            """
            Send a message to the active channel. Messages must be formatted as json. Schemas may be found in the channel's description.
            """
            try:
                json.loads(message)
            except:
                return "Invalid Json"
            try:
                ac = ""
                if tool:
                    ac = self.active_tool_channel
                else:
                    ac = self.active_chat_channel
                self.channels[ac]["client"].send(message)
                self.channels[ac]["messages"].append({"timestamp":time.localtime(), "from":"You", "text":message})
            except Exception as e:
                return f'Unknown error, exception: "{str(e)}"'
            return "Success"
        @function_tool
        def read_messages(page:int = 0,count:int = 5, tool:bool = False):
            """
            Read your message history for the currently active channel. May not be complete due to restarts, so make sure to keep important stuff in your memory.
            """
            ac = ""
            if tool:
                ac = self.active_tool_channel
            else:
                ac = self.active_chat_channel
            msgs = self.channels[ac]["messages"][0-((page+1)*count):][:count]
            return "\n".join([f"<{time.strftime("%d %b, %H:%M:%S",msg["timestamp"])}> ({msg["from"]}): {msg["text"]}" for msg in msgs])
        self.tools += [list_channels, set_active_channel,send_message,read_messages]

    def run(self, inp=None):
        print("[Agent Main] Agent running!")
        #print("[Agent Main] wake message: ", inp)
        agent = Agent(
            name="Agent",
            instructions = self.get_instructions_outer(),
            tools=self.tools, # type: ignore
            model=self.model,
        )
        
        hist = self.channels[self.active_chat_channel]["messages"][-5:]
        ctx = []
        for msg in hist:
            if msg["from"] == "you":
                ctx.append({"role":"assistant", "content":msg["text"]})
            else:
                ctx.append({"role":"user", "content":msg["text"]})

        if inp != None:
            ctx.append({"role":"user", "content":inp})
        #print(ctx)
        #out = Runner.run_sync(agent, "(Note: The following is an automated message.) "+ inp, max_turns=24)
        out = Runner.run_sync(agent, ctx, max_turns=24).final_output
        self.channels[self.active_chat_channel]["client"].send(json.dumps({"text":out}))
        self.channels[self.active_chat_channel]["messages"].append({"timestamp":time.localtime(), "from":"You", "text":out})
        print("[Agent Main] Agent done!")
        #for r in out.raw_responses:
        #    print(r)


def start():
    soul = ""
    try:
        with open("soul.txt") as f:
            soul = f.read()
    except FileNotFoundError:
        pass
    mem = ""
    try:
        with open("memory.txt") as f:
            mem = f.read()
    except FileNotFoundError:
        pass
    mem = mem.strip()
    am = AgentMain(mem, soul)
    print("[Agent Main] Running on localhost:8282")
    am.ws_server.serve_forever() # type: ignore
    print("[Agent Main] exiting!")
    mem = am.memory
    with open("memory.txt", "w") as f:
        f.write(mem)


if __name__ == "__main__":
    start()
