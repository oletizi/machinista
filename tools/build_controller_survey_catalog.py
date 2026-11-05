#!/usr/bin/env python3
"""Generate the static browser model inventory from our shared checklists."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.controller_survey_catalog import PROFILES,checklist
for profile in PROFILES:checklist(profile)
Path(__file__).resolve().parents[1].joinpath('web/controller-survey/catalog.json').write_text(json.dumps({k:v for k,v in PROFILES.items() if v['survey_required']},indent=2)+'\n',encoding='utf-8')
