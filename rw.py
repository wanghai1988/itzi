#! /usr/bin/python
# coding=utf8

# COPYRIGHT:    (C) 2015 by Laurent Courty
#
#               This program is free software under the GNU General Public
#               License (v3). Read the LICENCE file for details.

import numpy as np
from grass.pygrass import raster, utils
from grass.pygrass.messages import Messenger

# start messenger
msgr = Messenger(raise_on_error=True)

def format_opt_map(opt, mapset):
    """ analyse grass command line option
    and return a fully qualified map name 
    """

    if '@' in opt:
        return opt
    else:
        return opt + '@' + mapset


def write_sim_data(opt_h, opt_wse, h_grid_np1, z_grid, can_ovr,
                    sim_clock, list_h, list_wse):
    """write the numpy arrays as grass raster maps
    """

    if opt_h or opt_wse:
        msgr.message(_("Printing results, simulation time: %.1f ") %
                 round(sim_clock,1))
        if opt_h:
            # define new map name
            depth_map_name = gen_mapname_s(opt_h, sim_clock)
            # transform zero depth to NaN / NULL
            h_map = np.where(h_grid_np1 == 0, np.nan, h_grid_np1)
            # write raster
            write_raster(depth_map_name, h_map, can_ovr)
            msgr.message(_("Writting water depth map <%s> ") % depth_map_name)
            # add map name to the map list
            if depth_map_name not in list_h:
                list_h.append(depth_map_name)

        if opt_wse:
            # define new map name
            wse_map_name = gen_mapname_s(opt_wse, sim_clock)
            # transform zero depth in NULL
            wse_map = np.where(h_grid_np1 == 0, np.nan, h_grid_np1 + z_grid)
            # write raster
            write_raster(wse_map_name, wse_map, can_ovr)
            msgr.message(_("Writting water surface elevation map <%s> ") % wse_map_name)
            # add map name to the map list
            if wse_map_name not in list_wse:
                list_wse.append(wse_map_name)

    return list_h, list_wse

def gen_mapname_s(map_prefix, sim_clock):
    """ generate a map name from a prefix and a time in seconds
    """
    
    # length of the timestamp (in characters)
    tsl = 6
    # generate the timestamp
    timestamp = str(int(round(sim_clock,0))).zfill(tsl)
    
    return map_prefix + '_' + timestamp + 's'

def write_raster(raster_name, arr, can_ovr):
    """
    write a grass raster
    raster_name: the GRASS raster name
    arr: the array to be written in GRASS raster
    """
    if can_ovr == True and raster.RasterRow(raster_name).exist() == True:
        utils.remove(raster_name, 'raster')
        msgr.verbose(_("Removing raster map %s") % raster_name)
    with raster.RasterRow(raster_name, mode='w', mtype='DCELL') as newraster:
        newrow = raster.Buffer((arr.shape[1],), mtype='DCELL')
        for row in arr:
            newrow[:] = row[:]
            newraster.put_row(newrow)
    return 0
