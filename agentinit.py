import threading
import main
import importlib
import cli_chat as cli_chat
import time
import os

def start(target, d=False):
    t = threading.Thread(target=target)
    t.daemon = d
    t.start()

if __name__ == "__main__": #TODO: make everything async. Will do either soon (hctg) or for stardance.
    start(main.start, d=True)
    time.sleep(1) #PAIN
    
    for f in os.listdir("./channels/"): #This is truely one of the things i have ever written
        if f[-3:] == ".py":
            a = importlib.import_module("channels."+f[:-3])
            start(a.start, True) 

    cli_chat.run_chat()
    time.sleep(5) #Hopefully this temp fixes failure to save memory?