#!/usr/bin/env python3
"""Read untrusted survey JSON and derive a review file. Never activate a driver."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.controller_survey import read_report,review

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('survey',type=Path);p.add_argument('--output',type=Path);args=p.parse_args()
 try:
  result=review(read_report(args.survey));data=json.dumps(result,indent=2)+'\n'
  if args.output:
   with args.output.open('x',encoding='utf-8') as f:f.write(data)
  else:print(data,end='')
 except (ValueError,OSError) as e:p.exit(2,str(e)+'\n')
if __name__=='__main__':main()
