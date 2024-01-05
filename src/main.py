# UPDATE TIME: 2023-09-15
# FROM JOY
from coffea.nanoevents import NanoEventsFactory, BaseSchema
import glob
import json
import argparse
from config.selectionconfig import runsetting as rs
from analysis.dsmethods import extract_items
from analysis.runtask import *

with open(rs.INPUTFILE_PATH, 'r') as samplepath:
    data = json.load(samplepath)

fileset = data['Background']
fileset.update(data['Signal'])

if rs.TEST_MODE:
    if rs.FILE_SET_LOCAL:
        fileset = rs.FILE_SET
    else:
        fileset = extract_items(fileset, rs.PROCESS_NAME)

del data

lineup_jobs(fileset, rs, 2)
