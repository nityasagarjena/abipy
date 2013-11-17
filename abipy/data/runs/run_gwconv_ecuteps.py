#!/usr/bin/env python
"""G0W0 convergence study wrt ecuteps and the number of bands in W."""
from __future__ import division, print_function

import sys
import numpy as np
import os

import abipy.abilab as abilab
import abipy.data as abidata


def make_inputs():
    """
    Returns a tuple of 4 input files for SCF, NSCF, SCR, SIGMA calculations.
    These files are then used as templates for the convergence study
    wrt ecuteps and the number of bands in W.
    """
    structure = abidata.structure_from_ucell("SiC")
    pseudos = abidata.pseudos("14si.pspnc","6c.pspnc")

    global_vars = dict(
        istwfk="*1",
        paral_kgb=0,
        gwpara=2
        #accesswff=3
    )

    ecut = 5
    ecuteps = 2
    ngkpt = [4, 4, 4]
    shiftk = [0, 0, 0]

    inp = abilab.AbiInput(pseudos=pseudos, ndtset=4)

    inp.set_structure(structure)
    inp.set_variables(**global_vars)
    inp.set_kmesh(ngkpt=ngkpt, shiftk=shiftk)

    inp[1].set_variables(
		ecut=ecut,
        nband=10,
        tolvrs=1.e-8,
    )

    inp[2].set_variables(
		ecut=ecut,
        nband=25,
        tolwfr=1.e-8,
        iscf=-2
    )

    inp[3].set_variables(
        optdriver=3,
		ecut=ecut,
        ecutwfn=ecut,
        nband=20,
        symchi=1,
        inclvkb=0,
        ecuteps=ecuteps,
    )
        
    inp[4].set_variables(
        optdriver=4,
        nband=20,
        ecutwfn=ecut,
        ecutsigx=ecut,
        #ecutsigx=(4*ecut), ! This is problematic
		ecut=ecut,
        symsigma=1,
        ecuteps=ecuteps,
        )

    inp[4].set_kptgw(kptgw=[[0,0,0], [0.5, 0, 0]],
                     bdgw=[1, 8]
                     )

    return inp.split_datasets()

def build_flow(workdir="tmp_gwconv_ecuteps"):

    # Get our templates
    scf_inp, nscf_inp, scr_inp, sig_inp = make_inputs()
    
    ecuteps_list = np.arange(2, 8, 2)
    max_ecuteps = max(ecuteps_list)

    manager = abilab.TaskManager.from_user_config()
    flow = abilab.AbinitFlow(manager=manager, workdir=workdir)

    # Band structure workflow to produce the WFK file
    bands = abilab.BandStructureWorkflow(scf_inp, nscf_inp)
    flow.register_work(bands)

    # Build a workflow made of two SCR runs with different value of nband
    # Use max_ecuteps for the dielectric matrix (sigma tasks will 
    # read a submatrix when we test the convergence wrt to ecuteps.
    scr_work = abilab.Workflow()

    for inp in abilab.input_gen(scr_inp, nband=[10, 15]):
        inp.set_variables(ecuteps=max_ecuteps)
        scr_work.register(inp, deps={bands.nscf_task: "WFK"})

    flow.register_work(scr_work)

    # Do a convergence study wrt ecuteps, each workflow is connected to a
    # different SCR file computed with a different value of nband.

    # Build a list of sigma inputs with different ecuteps
    sigma_inputs = list(abilab.input_gen(scr_inp, ecuteps=ecuteps_list))

    for scr_task in scr_work:
        sigma_conv = abilab.SigmaConvWorkflow(wfk_node=bands.nscf_task, scr_node=scr_task, sigma_inputs=sigma_inputs)
        flow.register_work(sigma_conv)

    return flow.allocate()


def main():
    flow = build_flow()
    return flow.build_and_pickle_dump()


if __name__=="__main__":
    sys.exit(main())
