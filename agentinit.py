import threading
import main
import cli_chat
import shell_ws

def start(target, d=False):
    t = threading.Thread(target=target)
    t.daemon = d
    t.start()

if __name__ == "__main__":
    start(main.start, d=True)
    start(shell_ws.start, d=True)
    cli_chat.run_chat()