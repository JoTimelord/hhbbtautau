# This file contains custom event selection classes for the analysis.
# The classes are inherited from the BaseEventSelections class
# TECHNICALLY THIS SHOULD BE THE ONLY FILE THAT NEEDS TO BE MODIFIED FOR CUSTOM EVENT SELECTIONS
from .selutility import BaseEventSelections, Object
import operator as opr

def switch_selections(sel_name):
    selections = {
        'skim': mockskimEvtSel,
        'prelim': prelimEvtSel
    }
    return selections.get(sel_name, BaseEventSelections)

class mockskimEvtSel(BaseEventSelections):
    """Reduce event sizes"""
    def setevtsel(self, events):
        electron = Object(events, "Electron")
        muon = Object(events, "Muon")
        tau = Object(events, "Tau")

        e_mask = (electron.ptmask(opr.ge) & \
                electron.custommask('cbtightid', opr.ge) & \
                electron.absdxymask(opr.le) & \
                electron.absetamask(opr.le) & \
                electron.absdzmask(opr.le)
                )
        elec_nummask = electron.numselmask(opr.eq, e_mask)

        m_mask = (muon.ptmask(opr.ge) & \
                muon.absdxymask(opr.le) & \
                muon.absetamask(opr.le) & \
                muon.absdzmask(opr.le) & \
                muon.custommask('looseid', opr.eq) & \
                muon.custommask('isoid', opr.ge))
        muon_nummask = muon.numselmask(opr.eq, m_mask)

        tau_mask = (tau.ptmask(opr.ge) & \
                    tau.absetamask(opr.le) & \
                    tau.osmask())

        tau_nummask = tau.numselmask(opr.ge, tau_mask)

        self.objsel.add_multiple({"Electron Veto": elec_nummask,
                                "Muon Veto": muon_nummask,
                                "Tau Selections": tau_nummask})
  
        jet = Object(events, 'Jet')
        j_mask = (jet.ptmask(opr.ge) &
                  jet.absetamask(opr.le))

        j_nummask = jet.numselmask(opr.ge, j_mask)
        btagmask = jet.numselmask(opr.ge, jet.custommask('btag', opr.ge))

        self.objsel.add_multiple({"Jet Selection": j_nummask,
                                  "Jet Btag": btagmask})

        return None 
        
class prelimEvtSel(BaseEventSelections):
    """Custom event selection class for the preliminary event selection."""
    def setevtsel(self, events):
        jet = Object(events, 'Jet')
        j_mask = (jet.ptmask(opr.ge) &
                  jet.absetamask(opr.le) & 
                  jet.numselmask(opr.ge, jet.custommask('btag', opr.ge))) 

        j_nummask = jet.numselmask(opr.ge, j_mask)

        self.objsel.add(name="Jet Selection", selection=j_nummask)

        return None

class fineEvtSel(BaseEventSelections):
    """Custom event selection class for the fine event selection."""
    def selectlep(self, events):
        pass 