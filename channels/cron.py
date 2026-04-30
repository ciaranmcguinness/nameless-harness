import asyncio
import websockets
import json
import channellib
import sqlite3

URI = "ws://127.0.0.1:8282"

async def wait(ws:websockets.ClientConnection, cur:sqlite3.Cursor, id:int, tg:asyncio.TaskGroup):

    cur.execute("SELECT wait FROM jobs WHERE id = ?", (str(id)))
    time = cur.fetchone()[0]

    await asyncio.sleep(time)

    cur.execute("SELECT msg, repeat FROM jobs WHERE id = ?", (str(id)))
    r = cur.fetchone()
    if r == None:
        print("rugged!")
        return
    msg = r[0]
    rep = r[1]

    await channellib.simple_send_msg(msg, ws, True)
    match rep:
        case 0:
            cur.execute("DELETE FROM jobs WHERE ID = ?", (str(id)))
        case 2:
            tg.create_task(wait(ws, cur, id, tg))
            
        case _:
            pass

async def handle(ws, cur:sqlite3.Cursor, tg:asyncio.TaskGroup):
    while True:
        o = await ws.recv()
        try:
            msg = json.loads(o)
            c = msg["command"] #this channel\'s schema is {\"len\":(time to wait in seconds), \"message\":\"message you will be sent when waiting is done\", \"repeat\":\"[no|every restart|yes]\"}
            match c:
                case "help":
                    await channellib.simple_send_msg("""Available commands:
Create a new job: {"command":"new","len":(time to wait in seconds), "message":"message you will be sent when waiting is done", "repeat":"[no|every restart|yes] (optional, default no)"} 
List jobs: {"command":"list"}
Delete a job: {"command":"delete", "id":(id as int)}
Show this message: {"command":"help"}""", ws)
                case "new":
                    i = ["no","every restart", "yes"].index(str(msg.get("repeat", "no")).strip().lower())
                    cur.execute("INSERT INTO jobs(msg, wait, repeat)\nVALUES(?,?,?)", (msg["msg"], msg["len"], i))
                    id = cur.lastrowid
                    if id != None:
                        if i != 1:
                            tg.create_task(wait(ws, cur, id, tg))
                        await channellib.simple_send_msg(f"Success! ID: {id}", ws)
                    else:
                        await channellib.simple_send_msg(f"Inexplicable failure. It probably worked.", ws)
                case "list":
                    cur.execute("SELECT * FROM jobs")
                    l = "\n".join(map(lambda r: f"{r[0]}: {[f"lasts {r[2]} seconds", f"happens {r[2]} seconds after every startup",f"repeats every {r[2]} seconds"][r[3]]}. Message: \"{r[1]}\"",cur.fetchall()))
                    await channellib.simple_send_msg(l,ws)
                case "delete":
                    cur.execute("DELETE FROM jobs WHERE ID = ?", (str(msg["id"])))
                    await channellib.simple_send_msg(f"Success!", ws)
        except (websockets.ConnectionClosed):
            return
        except (json.JSONDecodeError, KeyError):
            await channellib.simple_send_msg('The previous message failed to parse. Reminder: schemas can be obtained via {"command":"help"}.', ws, True, "Invalid Json on last call to cron.")
            continue

async def serve(ws: websockets.ClientConnection):
    cx = sqlite3.connect("cron.db")
    cx.autocommit = True
    cur = cx.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY AUTOINCREMENT, msg VARCHAR(1024) NOT NULL, wait INTEGER NOT NULL, repeat INT NOT NULL)")
    async with asyncio.TaskGroup() as tg:
        cur.execute("SELECT id FROM jobs")
        resume = cur.fetchall()
        for j in resume:
            print(j)
            tg.create_task(wait(ws, cur, j[0], tg))
        tg.create_task(handle(ws,cur,tg))


async def main():
    async with websockets.connect(URI) as ws:
        await channellib.intro("Cron", "Channel for cron jobs. Get schema via {\"command\":\"help\"}", ws, True)

        print("[cron] ready")

        await serve(ws)


def start():
    asyncio.run(main())

if __name__ == "__main__":
    start()