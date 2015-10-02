#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MODULE:    t.sim.flood

AUTHOR(S): Laurent Courty

PURPOSE:   Simulate superficial water flows using a quasi-2D implementation
           of the Shallow Water Equations.
           See:
           De Almeida, G. & Bates, P., 2013. Applicability of the local
           inertial approximation of the shallow water equations to
           flood modeling. Water Resources Research, 49(8), pp.4833–4844.
           Sampson, C.C. et al., 2013. An automated routing methodology
           to enable direct rainfall in high resolution shallow water models.
           Hydrological Processes, 27(3), pp.467–476.

COPYRIGHT: (C) 2015 by Laurent Courty

           This program is free software under the GNU General Public
           License (v3). Read the LICENCE file for details.
"""

#%module
#% description: Simulate superficial flows using simplified shallow water equations
#% keywords: raster
#% keywords: Shallow Water Equations
#% keywords: flow
#% keywords: flood
#%end

#%option G_OPT_R_ELEV
#% key: in_z
#% description: Name of input elevation raster map
#% required: yes
#%end

#%option G_OPT_R_INPUT
#% key: in_n
#% description: Name of input friction coefficient raster map
#% required: yes
#%end

#%option G_OPT_R_INPUT
#% key: in_h
#% description: Name of input water depth raster map
#% required: no
#%end

#~ #%option G_OPT_R_INPUT
#~ #% key: in_y
#~ #% description: Name of input water surface elevation raster map
#~ #% required: no
#~ #%end

#~ #%option G_OPT_R_INPUT
#~ #% key: in_inf
#~ #% description: Name of input infiltration raster map
#~ #% required: no
#~ #%end

#%option G_OPT_STRDS_INPUT
#% key: in_rain
#% description: Name of input rainfall raster space-time dataset
#% required: no
#%end

#%option G_OPT_STRDS_INPUT
#% key: in_inflow
#% description: Name of input user flow raster space-time dataset
#% required: no
#%end

#%option G_OPT_R_INPUT
#% key: in_bc
#% description: Name of input boundary conditions type map
#% required: no
#%end

#%option G_OPT_STRDS_INPUT
#% key: in_bcval
#% description: Name of input boundary conditions values raster STDS
#% required: no
#%end


#%option G_OPT_STRDS_OUTPUT
#% key: out_h
#% description: Name of output water depth raster space-time dataset
#% required: no
#%end

#%option G_OPT_STRDS_OUTPUT
#% key: out_wse
#% description: Name of output water surface elevation space-time dataset
#% required: no
#%end

#~ #%option G_OPT_R_OUTPUT
#~ #% key: q_i
#~ #% description: Name of output flow raster map for x direction
#~ #% required: no
#~ #%end
#~ 
#~ #%option G_OPT_R_OUTPUT
#~ #% key: q_j
#~ #% description: Name of output flow raster map for y direction
#~ #% required: no
#~ #%end

#%option G_OPT_UNDEFINED
#% key: start_time
#% description: Start of the simulation in format yyyy-mm-dd HH:MM
#% required: no
#%end

#%option G_OPT_UNDEFINED
#% key: end_time
#% description: End of the simulation in format yyyy-mm-dd HH:MM
#% required: no
#%end

#%option G_OPT_UNDEFINED
#% key: sim_duration
#% description: Duration of the simulation after start_time, in HH:MM:SS
#% required: no
#%end

#%option G_OPT_UNDEFINED
#% key: record_step
#% description: Duration between two records, in HH:MM:SS
#% required: yes
#%end

import sys
import os
from datetime import datetime
import numpy as np
import cProfile
import pstats
import StringIO

import grass.script as grass
from grass.pygrass.gis.region import Region
from grass.pygrass.messages import Messenger

import simulation

# values to be passed to simulation
input_times = {'start':None,'end':None,'duration':None,'rec_step':None}
input_map_names = {'z': None, 'n': None, 'h_old': None,
            'rain': None, 'inf':None, 'bcval': None, 'bctype': None}

output_map_names = {'out_h':None, 'out_wse':None,
            'out_vx':None, 'out_vy':None, 'out_qx':None, 'out_qy':None}

def main():
    # start profiler
    pr = cProfile.Profile()
    pr.enable()

    # start messenger
    msgr = Messenger()

    # check input values
    read_input_value(options, flags)

    # start simulation
    sim = simulation.SuperficialFlowSimulation(
                        start_time=input_times['start'],
                        end_time=input_times['end'],
                        sim_duration=input_times['duration'],
                        record_step=input_times['rec_step'],
                        input_maps=input_map_names,
                        output_maps=output_map_names)

    #################
    # End profiling #
    #################
    pr.disable()
    stat_stream = StringIO.StringIO()
    sortby = 'time'
    ps = pstats.Stats(pr, stream=stat_stream).sort_stats(sortby)
    ps.print_stats(5)
    print stat_stream.getvalue()

def str_to_timedelta(inp_str):
    """Takes a string in the form HH:MM:SS
    and return a timedelta object
    """
    data = inp_str.split(":")
    hours = int(data[0])
    minutes = int(data[1])
    seconds = int(data[2])
    if hours < 0:
        raise ValueError
    if not 0 < minutes < 59 or not 0 < seconds < 59:
        raise ValueError
    obj_dt = timedelta(hours=hours,
                    minutes=minutes,
                    seconds=seconds)
    return obj_dt

def read_input_value(opts, fl):
    """Check the sanity of input values
    write them to relevant dicts
    """

    date_format = '%Y-%m-%d %H:%M'
    # record step
    try:
        input_times['rec_step'] = str_to_timedelta(opts['record_step'])
    except ValueError:
        msgr.fatal(_("{}: format should be HH:MM:SS".format(
                'record_step')))

    # check valid combination to get simulation duration
    b_dur = (opts['sim_duration']
                and not opts['start_time'] and not opts['end_time'])
    b_start_dur = (opts['start_time']
                and opts['sim_duration'] and not opts['end_time'])
    b_start_end = (opts['start_time']
                and opts['end_time'] and not opts['sim_duration'])
    if not (b_dur or b_start_dur or b_start_end):
        msgr.fatal(_(
        "accepted combinations: {d} alone, {s} and {d}, {s} and {e}").format(
                    d='sim_duration', s='start_time', e='end_time'))

    if opts['sim_duration']:
        try:
            input_times['duration'] = str_to_timedelta(opts['sim_duration'])
        except ValueError:
            msgr.fatal(_("{}: format should be HH:MM:SS".format(
                    'sim_duration')))

    if options['end_time']:
        try:
            input_times['end'] = datetime.strptime(opts['end_time'], date_format)
        except ValueError:
            msgr.fatal(_("{}: format should be yyyy-mm-dd HH:MM".format(
                        'end_time')))

    if opts['start_time']:
        try:
            input_times['start'] = datetime.strptime(opts['start_time'],
                                                    date_format)
        except ValueError:
            msgr.fatal(_("{}: format should be yyyy-mm-dd HH:MM".format(
                    'start_time')))
    else:
        # default to minimum representable datetime
        input_times['start'] = datetime.min



############
# old code #
############
def old_code

    ##############
    # input data #
    ##############

    # terrain elevation (m)
    with raster.RasterRow(options['in_z'], mode='r') as rast:
            z_grid = np.array(rast, dtype = np.float32)

    # water depth (m)
    if not options['in_h']:
        depth_grid = np.zeros(shape = (yr,xr), dtype = np.float32)
    else:
        with raster.RasterRow(options['in_h'], mode='r') as rast:
            depth_grid = np.array(rast, dtype = np.float32)

    # manning's n friction
    with raster.RasterRow(options['in_n'], mode='r') as rast:
            n_grid = np.array(rast, dtype = np.float32)

    # User-defined flows (m/s)
    ta_user_inflow, stds_inflow = rw.load_ta_from_strds(
                                    options['in_inflow'], mapset,
                                    sim_clock, sim_duration, yr, xr)
    
    # rainfall (mm/hr)
    #~ strds_rainfall = tgis.open_stds.open_old_stds(options['in_rain'], 'strds')
    ta_rainfall, stds_rainfall = rw.load_ta_from_strds(
                                    options['in_rain'], mapset,
                                    sim_clock, sim_duration, yr, xr)
    
    # infiltration (mm/hr)
    # for now, set to zeros
    inf_grid = np.zeros(shape = (yr,xr), dtype = np.float16)

    # Evaporation (mm/hr)
    # for now, set to zeros
    evap_grid = np.zeros(shape = (yr,xr), dtype = np.float16)

    # Boundary conditions type and value (for used-defined value)
    # only bordering value is evaluated
    # default type: 1
    # default value: 0
    type_bc = np.dtype([('t', np.uint8), ('v', np.float16)])
    BC_grid = np.ones(shape = (yr,xr), dtype = type_bc)
    BC_grid['v'] = 0
    if options['in_bc']:
        with raster.RasterRow(options['in_bc'], mode='r') as rast:
            BC_type = np.array(rast, dtype = np.uint8)
        BC_grid['t'] = np.copy(BC_type)
        del BC_type
    if options['in_bcval']:
        #~ with raster.RasterRow(options['in_bcval'], mode='r') as rast:
            #~ BC_value = np.array(rast, dtype = np.float32)
        ta_bcval, stds_bcval = rw.load_ta_from_strds(
                                    options['in_bcval'], mapset,
                                    sim_clock, sim_duration, yr, xr)
        BC_grid['v'] = ta_bcval.arr


    ########################
    # Create domain object #
    ########################
    domain = RasterDomain(
                arr_z=z_grid,
                arr_n=n_grid,
                arr_bc=BC_grid,
                region=region,
                arr_h=depth_grid,
                end_time=sim_duration,
                theta=0.7,
                hmin=0.001)


    ###############
    # output data #
    ###############
    # list of written maps:
    list_h = []
    list_wse = []

    #####################################
    # Create output space-time datasets #
    #####################################

    stds_h_id, stds_wse_id = stds.create_stds(
        mapset, options['out_h'], options['out_wse'],
        sim_start_time, can_ovr)


    #####################
    # START COMPUTATION #
    #####################
    # time-step counter
    Dt_c = 1

    # Start time-stepping
    while not domain.sim_clock >= domain.end_time:
        #########################
        # write simulation data #
        #########################
        if domain.sim_clock / record_t >= record_count:
            list_h, list_wse = rw.write_sim_data(
                options['out_h'], options['out_wse'], domain.arr_h_np1,
                domain.arr_z, can_ovr, domain.sim_clock, list_h, list_wse)
            # update record count
            record_count += 1
            # set next forced timestep
            domain.set_forced_timestep(record_count * record_t)
            # print grid volume
            #~ V_total = np.sum(depth_grid) * domain.cell_surf
            #~ domain.solve_gridvolume
            #~ grass.info(_("Total grid volume at time %.1f : %.3f ") %
                        #~ (round(domain.sim_clock,1), round(domain.grid_volume,3)))


        ###########################
        # calculate the time-step #
        ###########################
        # calculate time-step and update the simulation counter
        domain.set_dt()

        # display percentage of simulation
        msgr.percent(domain.sim_clock, domain.end_time, 1)

        #######################
        # time-variable input #
        #######################
        # update user_inflow if no longer valid for that simulation time
        if not ta_user_inflow.is_valid(domain.sim_clock):
            msgr.verbose(_("updating user_inflow map"))
            ta_user_inflow = stds.update_time_variable_input(
                                                        stds_inflow,
                                                        domain.sim_clock)
            # update the domain object with ext_grid
            domain.set_arr_ext(ta_rainfall.arr, evap_grid,
                            inf_grid, ta_user_inflow.arr)

        if not ta_rainfall.is_valid(domain.sim_clock):
            msgr.verbose(_("updating rainfall map"))
            ta_rainfall = stds.update_time_variable_input(
                                                        stds_rainfall,
                                                        domain.sim_clock)
            # update the domain object with ext_grid
            domain.set_arr_ext(ta_rainfall.arr, evap_grid,
                            inf_grid, ta_user_inflow.arr)

        if options['in_bcval'] and not ta_bcval.is_valid(domain.sim_clock):
            msgr.verbose(_("updating BC values map"))
            ta_bcval = stds.update_time_variable_input(stds_bcval,
                                                    domain.sim_clock)
            # update the domain object
            domain.set_arr_bc(BC_grid)


        ############################
        # apply boudary conditions #
        ############################
        # apply boundary conditions
        # get the volume passing through the boundaries
        bound_vol = boundaries.apply_bc(
                                        domain.dict_bc,
                                        domain.arrp_z,
                                        domain.arrp_h,
                                        domain.arrp_q,
                                        domain.arrp_hf,
                                        domain.arrp_n,
                                        domain.dx,
                                        domain.dy,
                                        domain.dt,
                                        domain.g,
                                        domain.theta,
                                        domain.hf_min)

        # increase total volume change
        boundary_vol_total += bound_vol

        # assign values of boundaries
        #~ domain.arr_q_np1[:, 1]['W'] = domain.arr_q[:, 1]['W']  # W
        #~ domain.arrp_q_np1[1:-1, -1] = domain.arrp_q[1:-1, -1]  # E
        #~ domain.arrp_q_np1[0, 1:-1] = domain.arrp_q[0, 1:-1]    # N
        #~ domain.arr_q_np1[-1,:]['S'] = domain.arr_q[-1,:]['S']  # S


        ###################
        # calculate depth #
        ###################
        domain.solve_h()

        # assign values of boundaries
        #~ domain.arrp_h_np1[1:-1, 0] = domain.arrp_h[1:-1, 0]    # W
        #~ domain.arrp_h_np1[1:-1, -1] = domain.arrp_h[1:-1, -1]  # E
        #~ domain.arrp_h_np1[0, 1:-1] = domain.arrp_h[0, 1:-1]    # N
        #~ domain.arrp_h_np1[-1, 1:-1] = domain.arrp_h[-1, 1:-1]  # S


        ############################
        # mass balance calculation #
        ############################
        # calculate and display total grid volume
        domain.solve_gridvolume()
        grass.verbose(_("Domain volume at time %.1f : %.3f ") %
                        (round(domain.sim_clock,1), round(domain.grid_volume,3)))
        # calculate grid volume change
        Dvol = (np.sum(domain.arr_h_np1) - np.sum(domain.arr_h)) * domain.cell_surf
        domain.solve_ext_volume(bound_vol)
        ext_input = domain.total_ext_volume
        # calculate mass balance
        mass_balance = bound_vol + ext_input - Dvol
        # display mass balance
        grass.verbose(_("Mass balance at time %.1f : %.3f ") %
                        (round(domain.sim_clock, 1), round(mass_balance, 3)))

        ####################
        # Solve flow depth #
        ####################
        domain.solve_hflow()

        ####################################
        # Calculate flow inside the domain #
        ####################################
        domain.solve_q()

        #############################################
        # update simulation data for next time step #
        #############################################
        # update time-step counter
        Dt_c += 1

        # update the entry data
        domain.update_input_values()

        #####################
        # end of while loop #
        #####################


    ##############################
    # write last simulation data #
    ##############################
    
    list_h, list_wse = rw.write_sim_data(
        options['out_h'], options['out_wse'],
        domain.arr_h_np1, domain.arr_z,
        can_ovr, domain.sim_clock, list_h, list_wse)

    # print grid volume
    #~ V_total = np.sum(depth_grid) * domain.cell_surf
    #~ grass.info(_("Total grid volume at time %.1f : %.3f ") %
                #~ (round(sim_clock,1), round(V_total,3)))

    ########################################
    # register maps in space-time datasets #
    ########################################

    # depth
    if options['out_h']:
        list_h = ','.join(list_h) # transform map list into a string
        kwargs = {'maps': list_h,
                'start': 0,
                'unit':'seconds',
                'increment':int(record_t)}
        tgis.register.register_maps_in_space_time_dataset('rast',
                                                stds_h_id, **kwargs)


    # water surface elevation
    if options['out_wse']:
        list_wse = ','.join(list_wse)  # transform map list into a string
        kwargs = {'maps': list_wse,
                'start': 0,
                'unit':'seconds',
                'increment':int(record_t)}
        tgis.register.register_maps_in_space_time_dataset('rast',
                                                stds_wse_id, **kwargs)

    return 0


if __name__ == "__main__":
    options, flags = grass.parser()
    sys.exit(main())
