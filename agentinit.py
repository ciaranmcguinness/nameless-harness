import threading
import main
import channels.cli_chat as cli_chat
import channels.shell_ws as shell_ws
import channels.cron as cron
import time

def start(target, d=False):
    t = threading.Thread(target=target)
    t.daemon = d
    t.start()

if __name__ == "__main__": #TODO: make everything async. Will do either soon (hctg) or for stardance.
    start(main.start, d=True)
    time.sleep(1) #PAIN
    start(shell_ws.start, d=True)
    start(cron.start, d=True)
    cli_chat.run_chat()