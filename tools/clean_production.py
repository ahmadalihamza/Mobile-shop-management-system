"""Explicit administrator utility for the user-authorized clean production start."""
import argparse,json,sys,getpass
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mobile_desk.clean_start import clean_start
from mobile_desk.services.security import SecurityService

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--clean-start',action='store_true',required=True)
    p.add_argument('--owner',help='Configured owner username, when owner protection is enabled')
    args=p.parse_args()
    password=getpass.getpass('Owner password: ') if SecurityService(args.root).configured else None
    print(json.dumps(clean_start(args.root,username=args.owner,password=password),indent=2))
