#!/usr/bin/env python
# -*- coding: utf-8 -*-
############################################################################
#
# MODULE:       t.sim.flood
# AUTHOR(S):    Laurent Courty
#
# PURPOSE:      Simulate superficial water flow
#               Implementation of q-centered Numerical Scheme explained in:
#               G. A. M. de Almeida, P. Bates, J. E. Freer, and M. Souvignet
#               "Improving the stability of a simple formulation of the
#               shallow water equations for 2-D flood modeling", 2012
#               Water Resour. Res., 48, W05528, doi:10.1029/2011WR011570.
#
# COPYRIGHT:    (C) 2015 by Laurent Courty
#
#               This program is free software under the GNU General Public
#               License (v3). Read the file LICENCE for details.
#
#############################################################################

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

#~ #%option G_OPT_R_INPUT
#~ #% key: in_h
#~ #% description: Name of input water depth raster map
#~ #% required: no
#~ #%end

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

#%option G_OPT_R_INPUT
#% key: in_rain
#% description: Name of input rainfall raster map
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

#%option G_OPT_R_INPUT
#% key: in_bcval
#% description: Name of input boundary conditions value map
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
#% key: sim_duration
#% description: Duration of the simulation in seconds
#% required: yes
#%end

#%option G_OPT_UNDEFINED 
#% key: record_step
#% description: Duration between two records, in seconds
#% required: yes
#%end

import sys
from datetime import datetime
import math
import numpy as np

import rw
import boundaries
import hydro
import stds

from domain import RasterDomain

import grass.script as grass
import grass.temporal as tgis
from grass.pygrass import raster
from grass.pygrass.gis.region import Region

import cProfile, pstats, StringIO

def main():
    ##################
    # start profiler #
    ##################
    pr = cProfile.Profile()
    pr.enable()

    # get date and time at start
    start_time = datetime.now()

    #####################
    # general variables #
    #####################

    sim_t = int(options['sim_duration'])  # Simulation duration in s
    sim_clock = 0.0  # simulation time counter in s
    record_t =  int(options['record_step'])  # Recording time step in s
    record_count = 0  # Records counter

    # mass balance
    boundary_vol_total = 0  # volume passing through boundaries
    domain_vol_total = 0  # total domain volume at end of simulation

    # check if output maps can be overwritten
    can_ovr = grass.overwrite()

    # get current mapset
    mapset = grass.read_command('g.mapset', flags='p').strip()

    ####################################
    # set the temporal GIS environment #
    ####################################
    tgis.init()

    #######################
    # Grid related values #
    #######################
    region = Region()
    # grid size in cells
    xr = region.cols
    yr = region.rows
    
    # cell size in m
    dx = region.ewres
    dy = region.nsres

    # cell surface in m2
    dxdy = dx * dy
    

    ##############
    # input data #
    ##############

    # terrain elevation (m)
    with raster.RasterRow(options['in_z'], mode='r') as rast:
            z_grid = np.array(rast, dtype = np.float32)

    # water depth (m)
    #~ if not options['in_h']:
        #~ depth_grid = np.zeros(shape = (yr,xr), dtype = np.float64)
    #~ else:
        #~ with raster.RasterRow(options['in_h'], mode='r') as rast:
            #~ depth_grid = np.array(rast, dtype = np.float64)

    # define flow/depth data type
    type_faces = np.dtype([('W', np.float64), ('S', np.float64)])

    # flow (m3/s)
    flow_grid = np.zeros(shape = (yr,xr), dtype = type_faces)

    # flow depth: diff. between the highest water free surface of the two
    # adjacent cells and the highest terrain elev. (approx. of hyd. radius)
    hf_grid = np.zeros(shape = (yr,xr), dtype = type_faces)
     
    # manning's n friction
    with raster.RasterRow(options['in_n'], mode='r') as rast:
            n_grid = np.array(rast, dtype = np.float16)
    
    # rainfall (mm/hr)
    if not options['in_rain']:
        rain_grid = np.zeros(shape = (yr,xr), dtype = np.float16)
    else:
        with raster.RasterRow(options['in_rain'], mode='r') as rast:
            rain_grid = np.array(rast, dtype = np.float32)
    
    # infiltration (mm/hr)
    #~ if not options['in_inf']:
        #~ inf_grid = np.zeros(shape = (yr,xr), dtype = np.float16)
    #~ else:
        #~ with raster.RasterRow(options['in_inf'], mode='r') as rast:
            #~ inf_grid = np.array(rast, dtype = np.float32)
    # for now, set to zeros
    inf_grid = np.zeros(shape = (yr,xr), dtype = np.float16)

    # Evaporation (mm/hr)
    # for now, set to zeros
    evap_grid = np.zeros(shape = (yr,xr), dtype = np.float16)

    # User-defined flows (m/s)
    if not options['in_inflow']:
        user_grid = np.zeros(shape = (yr,xr), dtype = np.float16)
    else:
        #~ with raster.RasterRow(options['in_inflow'], mode='r') as rast:
            #~ ext_grid = np.array(rast, dtype = np.float32)
        opt_inflow = rw.format_opt_map(options['in_inflow'], mapset)
        inflow_dts = tgis.open_stds.open_old_stds(opt_inflow, 'strds')
        inflow_map_list = inflow_dts.get_registered_maps(columns='id,start_time,end_time,unit', order='start_time')


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
        with raster.RasterRow(options['in_bcval'], mode='r') as rast:
            BC_value = np.array(rast, dtype = np.float64)
        BC_grid['v'] = np.copy(BC_value)
        del BC_value


    #############################
    # Instantiate domain object #
    #############################
    
    domain = RasterDomain(
                arr_z = z_grid,
                arr_n = n_grid,
                #~ arr_rain = rain_grid,
                #~ arr_evap = evap_grid,
                #~ arr_inf = inf_grid,
                #~ arr_user = user_grid,
                arr_bc = BC_grid,
                #~ arr_h = depth_grid,
                region = region)


    
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
        start_time, can_ovr)


    #####################
    # START COMPUTATION #
    #####################
    # time-step counter
    Dt_c = 1

    # Start time-stepping
    while not sim_clock >= sim_t:

        #########################
        # write simulation data #
        #########################
        if sim_clock / record_t >= record_count:
            list_h, list_wse = rw.write_sim_data(
                options['out_h'], options['out_wse'], domain.arr_h_np1,
                domain.arr_z, can_ovr, sim_clock, list_h, list_wse)
            
            # update record count
            record_count += 1
            # print grid volume
            #~ V_total = np.sum(depth_grid) * domain.cell_surf
            #~ domain.solve_gridvolume
            #~ grass.info(_("Total grid volume at time %.1f : %.3f ") %
                        #~ (round(sim_clock,1), round(domain.grid_volume,3)))


        ###########################
        # calculate the time-step #
        ###########################
        # calculate time-step
        domain.solve_dt()
        # update the simulation counter
        sim_clock += domain.dt

        #######################
        # time-variable input #
        #######################

        for i, raster_map in enumerate(inflow_map_list):

            # if the map is the last, set the end time as end of simulation
            if i == len(inflow_map_list) - 1:
                end_time = max(sim_t,raster_map['start_time'])
            # else set end time as start time of the next map
            else:
                end_time = inflow_map_list[i+1]['start_time']

            # translate input in s
            if raster_map['unit'] == 'minutes':
                start_time_s = raster_map['start_time'] * 60
                end_time_s = end_time * 60

            # load the corresponding map
            if sim_clock >= start_time_s and sim_clock < end_time_s:
                #~ print sim_clock, raster_map['id']
                with raster.RasterRow(raster_map['id'], mode='r') as rast:
                    user_grid = np.array(rast, dtype = np.float32)

        # update the domain object with ext_grid
        domain.set_arr_ext(rain_grid, evap_grid, inf_grid, user_grid)


        ############################
        # apply boudary conditions #
        ############################
        # apply boundary conditions and get the volume passing through the boundaries
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
        #~ flow_grid_np1[:, 1]['W'] = flow_grid[:, 1]['W']              # W
        #~ flow_grid_np1_padded[1:-1, -1] = flow_grid_padded[1:-1, -1]  # E
        #~ flow_grid_np1_padded[0, 1:-1] = flow_grid_padded[0, 1:-1]    # N
        #~ flow_grid_np1_padded[-1, 1:-1] = flow_grid_padded[-1, 1:-1]  # S


        ###################
        # calculate depth #
        ###################
        domain.solve_h()

        # assign values of boundaries
        #~ h_grid_np1_padded[1:-1, 0] = depth_grid_padded[1:-1, 0]    # W
        #~ h_grid_np1_padded[1:-1, -1] = depth_grid_padded[1:-1, -1]  # E
        #~ h_grid_np1_padded[0, 1:-1] = depth_grid_padded[0, 1:-1]    # N
        #~ h_grid_np1_padded[-1, 1:-1] = depth_grid_padded[-1, 1:-1]  # S


        ############################
        # mass balance calculation #
        ############################

        #~ # calculate and display total grid volume        
        #~ V_total = np.sum(h_grid_np1) * dxdy
        #~ grass.verbose(_("Domain volume at time %.1f : %.3f ") %
                        #~ (round(sim_clock,1), round(V_total,3)))
        #~ 
        #~ # calculate grid volume change
        #~ Dvol = (np.sum(h_grid_np1) - np.sum(depth_grid)) * dxdy
#~ 
        #~ 
        #~ ext_input = np.sum(ext_grid * dxdy * dt)
#~ 
        #~ # calculate mass balance
        #~ mass_balance = bound_vol + ext_input - Dvol
#~ 
        #~ # display mass balance
        #~ grass.verbose(_("Mass balance at time %.1f : %.3f ") %
                        #~ (round(sim_clock, 1), round(mass_balance, 3)))

       
        ####################
        # Solve flow depth #
        ####################
        domain.solve_hflow()

        ####################################
        # Calculate flow inside the domain #
        ####################################
        domain.arr_q_np1 = hydro.get_flow(
            domain.arrp_z,
            domain.arrp_n,
            domain.arr_h,
            domain.arr_hf,
            domain.arrp_q,
            domain.arrp_h_np1,
            domain.arr_q_np1,
            domain.hf_min,
            domain.dt, domain.dx, domain.dy,
            domain.g, domain.theta)


        #############################################
        # update simulation data for next time step #
        #############################################
        # update time-step counter
        Dt_c += 1

        # update the entry data
        domain.update_input_values()

        #########################
        # end of while loop #
        #########################


    ##############################
    # write last simulation data #
    ##############################
    
    list_h, list_wse = rw.write_sim_data(
        options['out_h'], options['out_wse'], domain.arr_h_np1, domain.arr_z,
        can_ovr, sim_clock, list_h, list_wse)

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
        kwargs = {'maps': list_h, 'start': 0, 'unit':'seconds', 'increment':int(record_t)}
        tgis.register.register_maps_in_space_time_dataset('rast', stds_h_id, **kwargs)


    # water surface elevation
    if options['out_wse']:
        list_wse = ','.join(list_wse)  # transform map list into a string
        kwargs = {'maps': list_wse, 'start': 0, 'unit':'seconds', 'increment':int(record_t)}
        tgis.register.register_maps_in_space_time_dataset('rast', stds_wse_id, **kwargs)


    #################
    # End profiling #
    #################
    pr.disable()
    stat_stream = StringIO.StringIO()
    sortby = 'cumulative'
    ps = pstats.Stats(pr, stream=stat_stream).sort_stats(sortby)
    ps.print_stats(5)
    print stat_stream.getvalue()

    return 0


if __name__ == "__main__":
    options, flags = grass.parser()
    sys.exit(main())