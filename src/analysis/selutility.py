#!/usr/bin/env python

import awkward as ak
import dask_awkward as dak
from analysis.dsmethods import *
from coffea.analysis_tools import PackedSelection
from coffea.nanoevents import NanoEventsFactory
from coffea.nanoevents.schemas import BaseSchema
from coffea.nanoevents.methods import vector
import vector as vec
import uproot
import json as json
import operator
from collections import ChainMap

class Processor:
    def __init__(self):
        self._selseq = None
        self._data = None
        self._cutflow = 0
    
    @property
    def data(self):
        return self._data
    
    @data.setter
    def data(self, rt_cfg):
        with open(rt_cfg.INPUTFILE_PATH, 'r') as samplepath:
            fileset = json.load(samplepath)
        value = fileset['Background']
        value.update(fileset['Signal']) 
        self._data = value
        
    @property
    def selseq(self):
        return self._selseq
    
    @selseq.setter
    def selseq(self, value):
        self._selseq = value
        
    def evalute(self, events, leftover=True):
        pass
    
    def loadfile(self, filename, dsname, rt_cfg):
        events = NanoEventsFactory.from_root(
            file=f"{filename}:{rt_cfg.TREE_NAME}",
            steps_per_file= rt_cfg.CHUNK_NO,
            uproot_options={"timeout": 100},
            delayed=True,
            metadata={"dataset": dsname},
            schemaclass=BaseSchema,
        ).events()
        return events
        
    def testrun(self, rt_cfg):
        """Run test selections on a single file.

        :return: output
        """
        self.data = rt_cfg
        filename = f"{self.data['Background']['DYJets_1']}:Events"
        events = NanoEventsFactory.from_root(
            filename,
            entry_stop=None,
            metadata={"dataset": "DYJets"},
            schemaclass=BaseSchema,
        ).events()
        return out        
    

def lepton_selections(events, cfg):
    """ Preselect candidate events for a target process with major object selections.

    :param events: events in a NANOAD dataset
    :type events: coffea.nanoevents.NanoEvents.array
    :param cfg: configuration object
    :type cfg: DynaConf object
    :return events_dict: dictionary of coffea nanoevents array with major object selections.
             keys = channel names, values = events array
    :rtype events_dict: dict{int: coffea.nanoevents.NanoEvents.array}
    :return cutflow_dict: cutflow dictionary.
             Keys = Channel names, values = {
                 Keys = Selection name, Values = Event number
             }
    :rtype cutflow_dict: dict{dict: int}
    :return object_dict: dictionary of zipped objects
    :rtype object_dict: dict{object name: coffea.nanoevents.methods.vector.PtEtaPhiMLorentzVectorArray}
    """

    events_dict = {}
    cutflow_dict = {}
    object_dict = {}

    # Set up selections for the major candidates
    for i in range(cfg.signal.channelno):
        keyname = "".join(["channel", str(i+1)])
        # Create lepton objects
        muons, electrons, taus = zip_lepproperties(cfg.signal.outputs, events)
        # Create lepselection object: coffea.analysis_tool.PackedSelection
        lepselection = PackedSelection()
        lepcfgname = "signal.channel"+str(i+1)
        lepselname = cfg[lepcfgname+".selections"]
        # select electrons
        eselect = lepselname.electron
        if eselect.veto is not None:
            if not eselect.veto:
                electronmask = (electrons.pt > eselect.ptLevel) & \
                               (abs(electrons.eta) < eselect.absetaLevel) & \
                               (electrons.bdtid >= eselect.BDTLevel) & \
                               (abs(electrons.dxy) < eselect.absdxyLevel) & \
                               (abs(electrons.dz) < eselect.absdzLevel)
                electrons = electrons[electronmask]
                lepselection.add("ElectronSelection", ak.to_numpy(
                    ak.num(electrons) == eselect.count))
            # apply vetos
            else:
                electronmask = (electrons.pt > eselect.ptLevel)
                electrons = electrons[electronmask]
                lepselection.add("ElectronSelection",
                                 ak.to_numpy(ak.num(electrons) == 0))

        # select muons
        mselect = lepselname.muon
        if (mselect.veto is not None):
            if not mselect.veto:
                # TODO: figure out a way to construct the filtered muons quickly from fields
                muonmask = (muons.pt > mselect.ptLevel) & \
                           (abs(muons.eta) < mselect.absetaLevel) & \
                           (abs(muons.dxy) < mselect.absdxyLevel) & \
                           (abs(muons.dz) < mselect.absdzLevel) & \
                           (muons.iso < mselect.isoLevel) & \
                           (muons.tightid == mselect.IDLevel)
                muons = muons[muonmask]
                lepselection.add("MuonSelection", ak.to_numpy(
                    ak.num(muons) == mselect.count))
            else:
                muonmask = (muons.pt > mselect.ptLevel)
                muons = muons[muonmask]
                lepselection.add(
                    "MuonSelection", ak.to_numpy(ak.num(muons) == 0))

        # select taus
        tselect = lepselname.tau
        if tselect.veto is not None:
            if not tselect.veto:
                taumask = (taus.pt > tselect.ptLevel) & \
                    (abs(taus.eta) < tselect.absetaLevel) & \
                    (taus.idvsjet >= tselect.IDvsjetLevel) & \
                    (taus.idvsmu >= tselect.IDvsmuLevel) & \
                    (taus.idvse >= tselect.IDvseLevel) & \
                    (abs(taus.dz) < tselect.absdzLevel)
                taus = taus[taumask]
                lepselection.add("TauSelection", ak.to_numpy(
                    ak.num(taus) == tselect.count))
            else:
                # TODO: for now a placeholder
                pass

        # Evaluate the selection collections at this point to identify individual leptons selected
        cutflow_dict[keyname] = {}
        cutflow_dict[keyname]["Total"] = len(events)
        for i, sel in enumerate(lepselection.names):
            cutflow_dict[keyname][sel] = lepselection.all(
                *(lepselection.names[:i+1])).sum()
        all_lep_mask = lepselection.all(*(lepselection.names))
        events_dict[keyname] = events[all_lep_mask]
        object_dict[keyname] = {"Electron": electrons[all_lep_mask],
                                "Muon": muons[all_lep_mask],
                                "Tau": taus[all_lep_mask]}
        events = events[~(lepselection.all(*(lepselection.names)))]

    return events_dict, cutflow_dict, object_dict


def pair_selections(events_dict, cutflow_dict, object_dict, cfg):
    """ Place pair selections on candidate events belonging to parallel target processes.

    :param events_dict: events with object preselections in different channels organized by a dictionary.
    :type events_dict: dict{coffea.nanoevents.NanoEvents.array}
    :param cfg: configuration object
    :type cfg: DynaConf object
    :return: dictionary of coffea nanoevents array with major object selections
    :rtype: dict{int: coffea.nanoevents.NanoEvents.array}
    """

    for keyname, events in events_dict.items():
        lepcfgname = f"signal.{keyname}"
        lepselname = cfg[lepcfgname+".selections"]
        filter_muons = object_dict[keyname]['Muon']
        filter_electrons = object_dict[keyname]['Electron']
        filter_taus = object_dict[keyname]["Tau"]

        # select pair properties
        if lepselname.pair is not None:
            pairselect = lepselname.pair
            pairname = pairselect.name
            is_M = "M" in pairname
            is_T = "T" in pairname
            is_E = "E" in pairname
            if is_M and is_T:
                dR = (filter_muons[:, 0].delta_r(filter_taus) >= pairselect.dRLevel)
                OS = (filter_muons[:, 0]["charge"] * filter_taus["charge"] < 0)
                SS = (filter_muons[:, 0]["charge"] * filter_taus["charge"] > 0)
            elif is_E and is_T:
                dR = (filter_electrons[:, 0].delta_r(filter_taus) >= pairselect.dRLevel)
                OS = (filter_electrons[:, 0]["charge"] * filter_taus["charge"] < 0)
                SS = (filter_electrons[:, 0]["charge"] * filter_taus["charge"] > 0)
            elif pairname.count("T") == 2:
                # TODO: place holder for now for this channel
                dR = ak.ones_like(filter_taus['charge'])
                OS = ak.ones_like(filter_taus['charge'])
                SS = ak.ones_like(filter_taus['charge'])
            pairmask = dR & (OS if pairselect.OS else SS)
            filter_taus = filter_taus[pairmask]
            object_dict[keyname].update({"Tau": filter_taus})
            apply_mask_on_all(object_dict[keyname], ak.any(pairmask, axis=1))
            events = events[ak.any(pairmask, axis=1)]
        events_dict[keyname] = events
        cutflow_dict[keyname]["Pair Selection"] = len(events)


def jet_selections(events_dict, cutflow_dict, object_dict, cfg):
    """ Place jet selections on candidate events belonging to parallel target processes.

    :param events_dict: dictionary of coffea nanoevents array with major object selections and pair selections
    :type events_dict: dict{coffea.nanoevents.NanoEvents.array}
    :param cutflow_dict: dictionary of cutflows in different channels
    :type cutflow_dict: dict{keyname:{
            selection: int
            }
    :param object_dict: dictionary of zipped lepton objects
    :type object_dict: dict{object name: coffea.nanoevents.methods.vector.PtEtaPhiMLorentzVectorArray}
    :param cfg: configuration object
    :type cfg: DynaConf object
    """
    for keyname, events in events_dict.items():
        lepcfgname = f"signal.{keyname}"
        lepselname = cfg[lepcfgname+".selections"]
        comselname = cfg["signal.commonsel"]
        if comselname.ak4jet is not None:
            ak4s, ak8s = zip_jetproperties(cfg.signal.outputs, events)
            jetselect = comselname.ak4jet
            # Basic jet check
            ak4mask = (ak4s.pt > jetselect.ptLevel) & \
                (abs(ak4s.eta) < jetselect.absetaLevel)
            ak4s = ak4s[ak4mask]
            ak4mask = (ak.num(ak4s) >= jetselect.count)
            events = events[ak4mask]
            ak4s = ak4s[ak4mask]
            ak8s = ak8s[ak4mask]
            apply_mask_on_all(object_dict[keyname], ak4mask)
            # Overlap check
            if not lepselname.electron.veto and (lepselname.electron.veto is not None):
                electronLV = LV_from_zipped(object_dict[keyname]['Electron'])
                dRmask = (ak.sum(electronLV[:, 0].deltaR(LV_from_zipped(ak4s)) > jetselect.dRLevel,
                             axis=1) > jetselect.count)
                events = events[dRmask]
                ak4s = ak4s[dRmask]
                ak8s = ak8s[dRmask]
                apply_mask_on_all(object_dict[keyname], dRmask)
            if not lepselname.muon.veto and (lepselname.muon.veto is not None):
                muonLV = LV_from_zipped(object_dict[keyname]['Muon'])
                dRmask = (ak.sum(muonLV[:, 0].deltaR(LV_from_zipped(ak4s)) > jetselect.dRLevel,
                                 axis=1) > jetselect.count)
                events = events[dRmask]
                ak4s = ak4s[dRmask]
                ak8s = ak8s[dRmask]
                apply_mask_on_all(object_dict[keyname], dRmask)
            if not lepselname.tau.veto and (lepselname.tau.veto is not None):
                for i in range(lepselname.tau.count):
                    tauLV = LV_from_zipped(object_dict[keyname]['Tau'])
                    dRmask = (ak.sum(tauLV[:, i].deltaR(LV_from_zipped(ak4s)) > jetselect.dRLevel, axis=1) > jetselect.count)
                    events = events[dRmask]
                    ak4s = ak4s[dRmask]
                    ak8s = ak8s[dRmask]
                    apply_mask_on_all(object_dict[keyname], dRmask)
        # TODO: Fill in fatjet selection
        events_dict[keyname] = events
        cutflow_dict[keyname]["Jet selections"] = len(events)
        object_dict[keyname].update({"Jet": ak4s,
                                     "FatJet": ak8s})


def write_rootfiles(events_dict, cfg, filename):
    """ Write dictionary of events in Coffea array to rootfile with a given filename.

    :param events_dict: dictionary of coffea nanoevents array with major object selections and pair selections
    :type events_dict: dict{coffea.nanoevents.NanoEvents.array}
    :param cfg: configuration object
    :type cfg: DynaConf object
    :param filename: filename of the root file to write events to
    :type filename: str
    :return: message about writing # events to a particular file
    :rtype: str

    """
    with uproot.update(filename) as rootfile:
        for i, events in events_dict.items():
            channelname = cfg["signal.channel"+str(i)+".name"]
            muons, electrons, taus = zip_lepproperties(cfg.signal.outputs, events)
            ak4s, ak8s = zip_jetproperties(cfg.signal.outputs, events)
            rootfile[channelname].extend({
                "Muon": muons,
                "Electron": electrons,
                "Tau": taus,
                "Jet": ak4s,
                "FatJet": ak8s
            })
    msg = f"Writing {len(events)} to {filename}"

    return msg

def apply_mask_on_all(object_dict, mask):
    """Apply mask on all the objects in a dict

    :param object_dict: {object_name: zipped object}
    :type object_dict: dict
    :param mask: mask to apply selections
    :type mask: ak.array
    """
    for name, zipped in object_dict.items():
        object_dict[name] = zipped[mask]


class Object():
    def __init__(self, name, events, objcfg, selcfg):
        self._name = name
        self.objcfg = objcfg 
        self.selcfg = selcfg
        self.set_dakzipped(events)
    
    @property
    def name(self):
        return self._name
    @name.setter
    def name(self, value):
        self._name = value
    
    @property
    def dakzipped(self):
        return self._dakzipped
    def set_dakzipped(self, events):
        vars_dict = dict(ChainMap(*(self.objcfg.values())))
        zipped_dict = {}
        for name, nanoaodname in vars_dict.items():
            zipped_dict.update({name: events[nanoaodname]})
        zipped_object = dak.zip(zipped_dict)
        self._dakzipped = zipped_object

    def fourvector(self, events, sortbypt=True):
        object_ak = ak.zip({
        "pt": events[self.name+"_pt"],
        "eta": events[self.name+"_eta"],
        "phi": events[self.name+"_phi"],
        "M": events[self.name+"_mass"]
        })
        if sortbypt:
            object_ak = object_ak[ak.argsort(object_ak.pt, ascending=False)]
        object_LV = vec.Array(object_ak)
        return object_LV
    
    def numselmask(self, op):
        return op(dak.num(self.dakzipped), self.selcfg.count)
    
    def ptmask(self, op):
        return (self.dakzipped.pt, self.selcfg.ptLevel, op)
    
    def etamask(self, op):
        return op(abs(self.dakzipped.eta), self.selcfg.absetaLevel)
    
    def dxymask(self, op):
        return op(abs(self.dakzipped.dxy), self.selcfg.absdxyLevel)
    
    def dzmask(self, op):
        return op(abs(self.dakzipped.dz), self.selcfg.absdzLevel)
    
    def bdtmask(self, op):
        return op(self.dakzipped.bdtid, self.selcfg.BDTLevel)


# TODO: combine the two methods
def LV_from_zipped(zippedLep, sortbypt=True):
    object_ak = ak.zip({
        "pt": zippedLep.pt,
        "eta": zippedLep.eta,
        "phi": zippedLep.phi,
        "M": zippedLep.mass,
    })
    if sortbypt:
        object_ak = object_ak[ak.argsort(object_ak.pt, ascending=False)]
    object_LV = vec.Array(object_ak)
    return object_LV
    
def overlap_check(object1, object2):
    """
    Check overlap between two objects. Note: Object 1 should only contain one item per event.

    :param object1: Contains ID of the leptons
    :type object1: coffea.nanoevents.methods.vector.PtEtaPhiMLorentzVectorArray
    :param object2: Contains ID of the jet
    :type object2: coffea.nanoevents.methods.vector.PtEtaPhiMLorentzVectorArray

    """

    return 0


def events_todf(events, objects):
    """
    Converts filtered events array (after object selections, preferably) into pandas dataframe.
    This can be useful for applying combinatorial selections

    :param events: filtered events array
    :type events: coffea.nanoevents.methods.base.NanoEventsArray
    :param objects: selected objects
    :type objects: list
    :return df: filtered events dataframe
    :type df: pandas.DataFrame
    """
