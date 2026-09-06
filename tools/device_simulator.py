#!/usr/bin/env python3
"""HTTP device simulator for local cloud testing.
Usage:
  python tools/device_simulator.py --uid <DEVICE_UID> --token <TOKEN> --server http://127.0.0.1:8000
"""
import argparse, random, time, requests

def main():
    p=argparse.ArgumentParser(); p.add_argument('--uid',required=True); p.add_argument('--token',required=True); p.add_argument('--server',default='http://127.0.0.1:8000'); p.add_argument('--interval',type=float,default=5); args=p.parse_args()
    base=args.server.rstrip('/'); headers={'X-Device-UID':args.uid,'X-Device-Token':args.token}
    states={1:False,2:False,3:False,4:False}
    print('Simulator online. Ctrl+C to stop.')
    while True:
        try:
            requests.post(base+'/api/device/heartbeat/',json={'firmware_version':'sim-1.0.0'},headers=headers,timeout=5).raise_for_status()
            requests.post(base+'/api/device/telemetry/',json={'temperature_c':round(27+random.random()*3,2),'humidity_pct':round(68+random.random()*8,2),'recorded_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())},headers=headers,timeout=5).raise_for_status()
            r=requests.get(base+'/api/device/commands/',headers=headers,timeout=5); r.raise_for_status()
            for cmd in r.json()['commands']:
                ch=cmd['relay_channel']; states[ch]=cmd['state']; print(f"Command {cmd['id']}: relay {ch} -> {states[ch]}")
                a=requests.post(base+f"/api/device/commands/{cmd['id']}/ack/",json={'success':True,'actual_state':states[ch]},headers=headers,timeout=5); a.raise_for_status()
        except requests.RequestException as exc: print('Network/API error:',exc)
        time.sleep(args.interval)
if __name__=='__main__': main()
