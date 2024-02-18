#!/usr/bin/env python
# adapted from: https://github.com/bu-cms/bucoffea/blob/83daf25146d883df5131d0b50a51c0a6512d7c5f/bucoffea/helpers/dasgowrapper.py

import json, os, sys, subprocess
from tqdm import tqdm
import uproot
import ROOT

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
    file_prefix = "root://cmsxrootd.fnal.gov/" if prefix == 'local' else "root://cms-xrd-global.cern.ch/"
    if fpath.startswith("/store/"):
        return f"{file_prefix}{fpath}"
    elif fpath.startswith("file:") or fpath.startswith("root:"):
        return fpath
    else:
        return f"file://{fpath}"

def query_MCsamples(dspath, outputfn, must_include=None, prefix='local'):
    """ Query xrootd to find all filepaths to a given set of dataset names and find corresponding xsection for the dataset.
    :param dspath: path to json file containing dataset names
    :type dspath: string
    :param outputfn: path to output json file containing full dataset paths
    :type outputfn: string
    """
    with open(dspath, 'r') as ds:
        dsjson = json.load(ds)

    complete_dict = {}
    query_dsstr = lambda ds: "".join(["dataset=", ds])
    query_fistr = lambda ds: "".join(["file dataset=", ds])

    for name, dataset_list in tqdm(dsjson.items(), f"finding samples ..."):
        for dataset in dataset_list:
            dsnames = dasgo_query(query_dsstr(dataset))
            filelist = []
            for ds in dsnames:
                filelist += dasgo_query(query_dsstr(ds))

        if must_include is not None:
            dslist = [ds for ds in dslist if must_include in ds]
        query_file = lambda ds: "".join(["file dataset=", ds])
        file_query_list = list(map(query_file, dslist))
        to_flatten = list(map(dasgo_query, file_query_list))
        filelist = [item for sublist in to_flatten for item in sublist]
        filelist_xrootd = list(map(lambda file_name: xrootd_format(file_name, prefix), filelist))
        complete_dict.update({name: filelist_xrootd})

    with open(outputfn, 'w') as jsonfile:
        json.dump(complete_dict, jsonfile)

def info_dict(file_path, tree_name):
    """Return the number of raw events and weighted events of a file in a json dictionary"""
    nevents_wgt = 0
    nevents_raw = 0
    with uproot.open(file_path) as f:
        t = f.get("Runs")
        nevents_wgt = t["genEventSumw"].array(library="np").sum()
        nevents_raw = f.get("Events").num_entries
        result_dict = {
            file_path: {
                "weighted_events": nevents_wgt,
                "raw_events": nevents_raw
            }
        }
    return result_dict

def preprocess_files(inputfn, step_size=10000, tree_name="Events", process_name = "DYJets"):
    def chunkfile_dict(file_path, tree_name, step_size):
        with uproot.open(file_path) as file:
            print("=============", file_path, "=============")
            tree = file[tree_name]
            n_events = tree.num_entries
            steps = [[i, min(i + step_size, n_events)] for i in range(0, n_events, step_size)]
            result_dict = {
                file_path: {
                    "object_path": tree_name,
                    "steps": steps
                }
            }
        return result_dict
    with open(inputfn, 'r') as ds:
        dsjson = json.load(ds)

    input_dict = {}
    failed_dict = {}
    ds = process_name
    pathlist = dsjson[process_name]
    result = {}
    for path in tqdm(pathlist, desc=f"Finding sample {ds}"):
        try:
            result.update(generate_dict(path, tree_name, step_size))
        except Exception as e:
            print(f"Failed to find {path}: {e}")
            failed_dict.update({ds: path})
    if result != {}: input_dict.update({ds: result})

    outputfn = f"chunked/{process_name}.json"
    with open(outputfn, 'w') as jsonfile:
        json.dump(input_dict, jsonfile)

    errorfn = f"chunked/{process_name}_failed.json"
    if failed_dict != {}:
        with open(errorfn, 'w') as errorfile:
            json.dump(failed_dict, errorfile)

    return None

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
    # query_MCsamples("querystring.json", "datasets_global.json", "Run3Summer22EE", prefix='global')
    preprocess_files("datasets_local.json", step_size=200000, process_name="WZZ")
    print("Jobs finished!")


