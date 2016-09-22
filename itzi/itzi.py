#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NAME:      Itzï

AUTHOR(S): Laurent Courty

PURPOSE:   Simulate dynamic superficial water flows using a simplified
           quasi-2D implementation of the Shallow Water Equations.
           See:
           De Almeida, G. & Bates, P., 2013. Applicability of the local
           inertial approximation of the shallow water equations to
           flood modeling. Water Resources Research, 49(8), pp.4833–4844.
           Sampson, C.C. et al., 2013. An automated routing methodology
           to enable direct rainfall in high resolution shallow water models.
           Hydrological Processes, 27(3), pp.467–476.

COPYRIGHT: (C) 2015-2016 by Laurent Courty

            This program is free software; you can redistribute it and/or
            modify it under the terms of the GNU General Public License
            as published by the Free Software Foundation; either version 2
            of the License, or (at your option) any later version.

            This program is distributed in the hope that it will be useful,
            but WITHOUT ANY WARRANTY; without even the implied warranty of
            MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
            GNU General Public License for more details.
"""


from __future__ import print_function, division
import sys
import os
import argparse
import time
import subprocess
import numpy as np
from multiprocessing import Process, Pipe
from pyinstrument import Profiler
from datetime import timedelta

from configreader import ConfigReader
import messenger as msgr


def main():
    args = parser.parse_args()
    args.func(args)


class SimulationRunner(object):
    """provide the necessary tools to run one simulation
    including reading configuration file, setting-up GRASS
    """
    def __init__(self, conf_file, grass_use_file):
        self.conf_file = conf_file
        self.file_name = os.path.basename(conf_file)
        self.grass_use_file = grass_use_file
        # default computational time. Updated by run()
        self.comp_time = timedelta(seconds=0)

    def run(self):
        """
        """
        # parsing configuration file
        conf = ConfigReader(self.conf_file)
        # If run outside of grass, set it
        if self.grass_use_file:
            self.set_grass_session(conf.grass_params)
            import grass.script as gscript
        # return error if output files exist
        # (should be done once GRASS set up)
        conf.check_output_files()

        # display parameters (if verbose)
        conf.display_sim_param()
        # stop program if location is latlong
        if gscript.locn_is_latlong():
            msgr.fatal(u"latlong location is not supported. "
                       u"Please use a projected location")
        # Run simulation (SimulationManager needs GRASS, so imported now)
        from simulation import SimulationManager
        msgr.message(u"Starting simulation "
                     u"for configuration file {}...".format(self.file_name))
        sim_start = time.time()
        sim = SimulationManager(sim_times=conf.sim_times,
                                stats_file=conf.stats_file,
                                dtype=np.float32,
                                input_maps=conf.input_map_names,
                                output_maps=conf.output_map_names,
                                sim_param=conf.sim_param)
        sim.run()
        self.comp_time = timedelta(seconds=int(time.time() - sim_start))
        # delete the rcfile
        if self.grass_use_file:
            os.remove(self.rcfile)
        return self

    def set_grass_session(self, grass_params):
        """Inspire by example on GRASS wiki
        """
        grassbin = grass_params['grass_bin']
        gisdb = grass_params['grassdata']
        location = grass_params['location']
        mapset = grass_params['mapset']

        # query GRASS 7 itself for its GISBASE
        gisbase = self.get_gisbase(grassbin)

        # set ldpath
        self.set_ldpath(gisbase)

        # Set GISBASE environment variable
        os.environ['GISBASE'] = gisbase

        # define GRASS Python environment
        sys.path.append(os.path.join(gisbase, "etc", "python"))

        # launch session
        import grass.script.setup as gsetup
        self.rcfile = gsetup.init(gisbase, gisdb, location, mapset)

        #~ import grass.script as gscript
        #~ import grass.temporal as tgis
        #~ import grass.temporal.core as tgiscore
        #~ print("g.mapset -p")
        #~ gscript.run_command('g.mapset', flags='p')
        #~ print("g.mapsets -p")
        #~ gscript.run_command('g.mapsets', flags='p')
        #~ # set up TGIS
        #~ conf_tgis = gscript.parse_command('t.connect', flags='cpg')
        #~ os.environ['TGISDB_DRIVER'] = conf_tgis['driver']
        #~ os.environ['TGISDB_DATABASE'] = conf_tgis['database']
        #~ ciface = tgis.CLibrariesInterface()
        #~ tgiscore._init_tgis_c_library_interface()
        #~ print("ciface.available_mapsets()")
        #~ print(ciface.available_mapsets())
        #~ print("get_available_temporal_mapsets()")
        #~ print(tgiscore.get_available_temporal_mapsets())
        #~ tgis.init(raise_fatal_error=True)
        return self

    def set_ldpath(self, gisbase):
        """Add GRASS libraries to the dynamic library path
        And then re-execute the process to take the changes into account
        """
        # choose right path for each platform
        if (sys.platform.startswith('linux')
                or 'bsd' in sys.platform
                or 'solaris' in sys.platform):
            ldvar = 'LD_LIBRARY_PATH'
        elif sys.platform.startswith('win'):
            ldvar = 'PATH'
        elif sys.platform == 'darwin':
            ldvar = 'DYLD_LIBRARY_PATH'
        else:
            msgr.fatal("Platform not configured: {}".format(sys.platform))

        ld_base = os.path.join(gisbase, "lib")
        try:
            if ld_base not in os.environ[ldvar]:
                os.environ[ldvar] += os.pathsep + ld_base
                self.reexec()
        except KeyError:
            if ldvar not in os.environ:
                os.environ[ldvar] = ld_base
                self.reexec()

    def reexec(self):
        """Re-execute the software with the same arguments
        """
        try:
            os.execv(sys.argv[0], sys.argv)
        except Exception, exc:
            msgr.fatal('Failed to re-exec')

    def get_gisbase(self, grassbin):
        """query GRASS 7 itself for its GISBASE
        """
        startcmd = [grassbin, '--config', 'path']
        try:
            p = subprocess.Popen(startcmd, shell=False,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = p.communicate()
        except OSError as error:
            msgr.fatal("Cannot find GRASS GIS start script"
                       " {cmd}: {error}".format(cmd=startcmd[0], error=err))
        if p.returncode != 0:
            msgr.fatal("Issues running GRASS GIS start script"
                       " {cmd}: {error}".format(cmd=' '.join(startcmd), error=err))
        return out.strip(os.linesep)


def sim_runner_worker(conn, conf_file, grass_use_file):
    #~ time.sleep(0.001)
    sim_runner = SimulationRunner(conf_file, grass_use_file)
    sim_runner.run()
    conn.send((sim_runner.file_name, sim_runner.comp_time))
    conn.close()


def itzi_run(args):
    # Check if being run within GRASS session
    try:
        import grass.script as gscript
    except ImportError:
        grass_use_file = True
    else:
        grass_use_file = False
    # start profiler
    if args.p:
        prof = Profiler()
        prof.start()

    # set environment variables
    if args.o:
        os.environ['GRASS_OVERWRITE'] = '1'
    else:
        os.environ['GRASS_OVERWRITE'] = '0'
    if args.v:
        os.environ['GRASS_VERBOSE'] = '3'
    else:
        os.environ['GRASS_VERBOSE'] = '2'

    # start total time counter
    total_sim_start = time.time()
    # dictionary to store computation times
    times_dict = {}
    for conf_file in args.config_file:
        parent_conn, child_conn = Pipe()
        # run in a subprocess
        worker_args = (child_conn, conf_file, grass_use_file)
        p = Process(target=sim_runner_worker, args=worker_args)
        p.start()
        # store computational time
        file_name, comp_time = parent_conn.recv()
        parent_conn.close()
        #~ child_conn.close()
        p.join()
        times_dict[file_name] = comp_time
    # stop total time counter
    total_elapsed_time = timedelta(seconds=int(time.time() - total_sim_start))
    # end profiling and print results
    if args.p:
        prof.stop()
        print(prof.output_text(unicode=True, color=True))
    # display total computation duration
    msgr.message(u"Simulations complete. Elapsed times:")
    for f, t in times_dict.iteritems():
        msgr.message(u"{}: {}".format(f, t))
    msgr.message(u"Total: {}".format(total_elapsed_time))
    avg_time_s = int(total_elapsed_time.total_seconds() / len(times_dict))
    msgr.message(u"Average: {}".format(timedelta(seconds=avg_time_s)))


def itzi_version(args):
    """Display the software version number from a file
    """
    ROOT = os.path.dirname(__file__)
    F_VERSION = os.path.join(ROOT, 'data', 'VERSION')
    with open(F_VERSION, 'r') as f:
        print(f.readline().strip())


########################
# Parsing command line #
########################

DESCR = (u"A dynamic, fully distributed hydraulic and hydrologic model. "
         u"Must be run within a GRASS GIS environment.")

parser = argparse.ArgumentParser(description=DESCR)
subparsers = parser.add_subparsers()

# running a simulation
run_parser = subparsers.add_parser("run", help=u"run a simulation",
                                   description="run a simulation")
run_parser.add_argument("config_file", nargs='+',
                        help=u"an Itzï configuration files (if several given, run in batch mode)")
run_parser.add_argument("-o", action='store_true', help=u"overwrite files if exist")
run_parser.add_argument("-p", action='store_true', help=u"activate profiler")
run_parser.add_argument("-v", action='store_true', help=u"verbose output")
run_parser.set_defaults(func=itzi_run)

# display version
version_parser = subparsers.add_parser("version",
                                       help=u"display software version number")
version_parser.set_defaults(func=itzi_version)


if __name__ == "__main__":
    sys.exit(main())
