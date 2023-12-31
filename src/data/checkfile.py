import uproot as uproot
import json
from tqdm import tqdm
from updatepath import dasgo_query, xrootd_format

def find_branches(file_path, object_list):
    """ Return a list of branches for each object in object_list

    :param file_path: path to the root file
    :param object_list: list of objects to find branches for
    :return: dictionary of branches for each object
    :rtype: dict
    """
    # Open the root file
    file = uproot.open(file_path)

    # Get the tree. Assuming the tree name is "Events"
    tree = file["Events"]

    # Get all branch names
    branch_names = tree.keys()

    # Initialize a dictionary to hold the branches for each object
    branches = {}

    # Filter branch names that start with each object
    for object in object_list:
        branches[object] = [name for name in branch_names if name.startswith(object)]

    return branches

def output_branches(in_fipath, out_fipath, checklist):
    """ Write the branches to a file.

    :param in_fipath: path to the root file
    :param out_fipath: path to the output file
    :param checklist: list of objects to find branches for
    """
    branches = find_branches(in_fipath, checklist)
    with open(out_fipath, 'w') as f:
        for object, object_branches in branches.items():
            f.write(f"{object} branches:\n")
            for branch in object_branches:
                f.write("%s\n" % branch)
            f.write("\n")

if __name__ == "__main__":
    checklist = ['Electron_', 'Muon_', 'Tau_', 'Jet_', 'FatJet_']
    inputfile = "MCsamplepath.json"
    with open (inputfile, 'r') as f:
        data = json.load(f)
        filedicts = {}
        filedicts.update(data['Signal'])
        filedicts.update(data['Background'])
        for process, datasets in tqdm(filedicts.items(), desc="Processing files"):
            for dataset in datasets:
                try:
                    sample = dasgo_query(f"dataset={dataset}")[0]
                    finame = sample.split('/')[1]
                    print(f"Writing to file {finame}.txt")
                    sample = dasgo_query(f"file dataset={sample}")[0]
                    sample = xrootd_format(sample)
                    output_branches(sample, f"objectchecks/{finame}.txt", checklist)
                except IndexError:
                    print(f"No data returned for dataset {dataset}")

