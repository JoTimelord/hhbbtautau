#!/usr/bin/env python
# adapted from: https://github.com/bu-cms/bucoffea/blob/83daf25146d883df5131d0b50a51c0a6512d7c5f/bucoffea/helpers/dasgowrapper.py

import subprocess
import json
import os
from tqdm import tqdm

def dasgo_query(query, json=False):
    cmd = ["dasgoclient", "--query", query]
    if json:
        cmd.append("-json")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)

    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Could not run DAS Go client query: {query}. Stderr: \n{stderr}")

    return stdout.decode().splitlines()

def xrootd_format(fpath, prefix):
    """Ensure that the file path is file:/* or xrootd"""
    file_prefix = "root://cmsxrootd.fnal.gov/" if prefix=="local" else "root://cms-xrd-global.cern.ch/"
    if fpath.startswith("/store/"):
        return f"{file_prefix}{fpath}"
    elif fpath.startswith("file:") or fpath.startswith("root:"):
        return fpath
    else:
        return f"file://{fpath}"

def query_MCsamples(dspath, outputfn, must_include=None, prefix='local'):
    """ Query xrootd to find all filepaths to a given set of dataset names.
    :param dspath: path to json file containing dataset names
    :type dspath: string
    :param outputfn: path to output json file containing full dataset paths
    :type outputfn: string
    """
    with open(dspath, 'r') as ds:
        dsjson = json.load(ds)

    complete_dict = {}

    for process in dsjson.keys():
        complete_dict[process] = {}
        for name, sample_list in tqdm(dsjson[process].items(), f"finding {process} samples..."):
            # make dataset query for a list of dataset in one process
            query_ds = lambda ds: "".join(["dataset=", ds])
            ds_query_list = list(map(query_ds, sample_list))
            to_flatten = list(map(dasgo_query, ds_query_list))
            dslist = [item for sublist in to_flatten for item in sublist]
            if must_include is not None:
                dslist = [ds for ds in dslist if must_include in ds]
            query_file = lambda ds: "".join(["file dataset=", ds])
            file_query_list = list(map(query_file, dslist))
            to_flatten = list(map(dasgo_query, file_query_list))
            filelist = [item for sublist in to_flatten for item in sublist]
            filelist_xrootd = list(map(xrootd_format, filelist, prefix))
            complete_dict[process].update({name: filelist_xrootd})

    with open(outputfn, 'w') as jsonfile:
        json.dump(complete_dict, jsonfile)

def divide_samples(inputfn, outputfn, dict_size=5):
    """Divide the ds into smaller list as value per key.

    :param inputfn: path to json file containing dataset names. With structure:
        {processname: [list of filenames]}
    :type inputfn: string
    :param outputfn: path to output json file containing full dataset paths
    :type outputfn: string
        {
            processname1: [list of 5 filenames]
            processname2: [list of 5 filenames]
            processname3: [list of 5 filenames]
            ...
        }
    :param dict_size: size of the list as keys
    :type dict_size: int
    """
    with open(inputfn, 'r') as jsonfile:
        dsjson = json.load(jsonfile)

    complete_dict = {}

    for process, processlist in dsjson.items():
        complete_dict.update({process: {}})
        for dsname, itemlist in processlist.items():
            n_dicts = len(itemlist) // dict_size + (len(itemlist) % dict_size > 0)

        # Create the smaller dictionaries
            smaller_dicts = {f"{dsname}_{i+1}": itemlist[i*dict_size:(i+1)*dict_size] for i in range(n_dicts)}
            complete_dict[process].update(smaller_dicts)

    with open(outputfn, 'w') as jsonfile:
        json.dump(complete_dict, jsonfile)

if __name__ == "__main__":
    query_MCsamples("MCsamplepath.json", "completepath.json", "Run3Summer22EE", prefix='global')
    divide_samples("completepath.json", "inputfile.json", 5)



