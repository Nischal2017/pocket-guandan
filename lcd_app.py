"""App-window protocol v1: foreground-only A and fingerprint gestures."""
import argparse,asyncio,socket,struct
from pocket import Table
from ui_text import LANGUAGES
SVC='ai.pamir.Lapis1'; MGR=SVC+'.AppWindowManager'; PATH='/ai/pamir/Lapis1/AppWindowManager'; HDR=struct.Struct('<4sHHHHIIIQQQII')
async def main(opening_seed=None, lang='en', difficulty='hard'):
    from dbus_fast.aio import MessageBus
    from dbus_fast import Message,MessageType,BusType
    t=Table(opening_seed, lang=lang, difficulty=difficulty);bus=await MessageBus(bus_type=BusType.SYSTEM,negotiate_unix_fd=True).connect();loop=asyncio.get_running_loop()
    async def call(method,sig='',body=(),fds=()):
        r=await bus.call(Message(destination=SVC,path=PATH,interface=MGR,member=method,signature=sig,body=list(body),unix_fds=list(fds)))
        if r.message_type==MessageType.ERROR:raise RuntimeError(method,r.error_name,r.body)
        return r.body
    caps=(await call('GetInputCapabilities'))[0]
    if caps&3!=3:raise RuntimeError('Missing focused-input or back support')
    srv,sock=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
    with srv,sock:
        sock.setblocking(False);win=await call('CreateWindow','ssh',['Guandan Hard' if difficulty=='hard' else 'Guandan Hand','gamepad',0],[srv.fileno()]);srv.close();print('window:',win,flush=True)
        ident=None;seq=last_input=0;shown=False
        while True:
            pkt=await loop.sock_recv(sock,1024)
            if not pkt:break
            _,_,kind,_,fl,wid,wg,vg,serial,token,ns,_,_=HDR.unpack_from(pkt);grant=(wid,wg,vg,token)
            if kind==2:
                seq=last_input=0;ident=grant if fl&1 else None;t.focus(bool(ident));print('visible:',bool(ident),flush=True)
            elif kind==3 and ident==grant:
                t.tick();frame=t.frame();seq+=1
                sock.send(HDR.pack(b'LPFW',1,1,HDR.size,15,wid,wg,vg,seq,token,0,len(frame),0)+frame)
            elif kind==8 and ident==grant and serial>last_input:
                if serial!=last_input+1:t.clear_input()
                last_input=serial;t.input(fl,ns/1e9)
            elif kind==4 and not shown:shown=True;print('first frame presented; focused gesture routing requested',flush=True)
            elif kind==6:break
    bus.disconnect()
def parse_args(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--opening-seed',type=int,help='Reproducible first deal only; replays are shuffled normally.')
    parser.add_argument('--lang', choices=LANGUAGES, default='en', help='Display language (default: en).')
    parser.add_argument('--difficulty', choices=('classic','hard'), default='hard',
                        help='Opponent difficulty. Your partner stays Classic in both modes.')
    return parser.parse_args(argv)

if __name__=='__main__':
    args=parse_args()
    asyncio.run(main(args.opening_seed, args.lang, args.difficulty))
