# UPDATE TIME: 2023-09-15
# FROM JOY
import uproot
from coffea.nanoevents import NanoEventsFactory, BaseSchema
from analysis.processing import *
from tqdm import tqdm
import glob
import json
import argparse
from config.selectionconfig import runsetting as rs

with open(rs.INPUTFILE_PATH, 'r') as samplepath:
    data = json.load(samplepath)

if not rs.TEST_MODE:
    # TODO: Place holder for now
    pass
else:
    filename = "root://cmsxrootd.fnal.gov//store/mc/Run3Summer22EENanoAODv11/DYJetsToLL_M-50_TuneCP5_13p6TeV-madgraphMLM-pythia8/NANOAODSIM/forPOG_126X_mcRun3_2022_realistic_postEE_v1-v1/70000/53a25c82-3fe6-4604-baa5-64d452496373.root"
    file = uproot.open(filename)
    events = NanoEventsFactory.from_root(
        file,
        entry_stop=10000,
        metadata={"dataset": "DYJets"},
        schemaclass=BaseSchema,
    ).events()
    # fileset = {'DYJets': data['Background']['DYJets']}
    p = hhbbtautauProcessor()
    out = p.process(events)
    output_export(out)
#    iterative_run = processor.Runner(
#        executor=processor.IterativeExecutor(desc="Executing fileset",compression=None),
#        schema=BaseSchema,
#    )
#    out = iterative_run(
#        fileset,
#        treename=rs.TREE_NAME,
#        processor_instance=hhbbtautauProcessor()
#    )


