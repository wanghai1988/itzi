# t.sim.flood
A GRASS GIS 7 module that simulates 2D superficial flows using simplified shallow water equations

# Description
This module is aimed at modelling floodplain inundations using simplified shallow water equations.
As of November 2015, it is under heavy development and subject to many kinds of changes and bugs.

It implements the q-centered numerical scheme described in:

De Almeida, G. a M. et al., 2012.
Improving the stability of a simple formulation of the shallow water equations for 2-D flood modeling.
Water Resources Research, 48(5), pp.1–14.

De Almeida, G. a M. & Bates, P., 2013.
Applicability of the local inertial approximation of the shallow water equations to flood modeling.
Water Resources Research, 49(8), pp.4833–4844.

As well as a simple rain routing method inspired by:

Sampson, C.C. et al., 2013.
An automated routing methodology to enable direct rainfall in high resolution shallow water models.
Hydrological Processes, 27(3), pp.467–476.

It outputs space-time raster datasets of:
  - water depth
  - water surface elevation (depth + DEM)

# Validity
To be completed

# Usage
## Input data
Note: the module does not support Lat-Long coordinates.
The inputs maps could be given either as STRDS or single maps.
First, the module try to load a STRDS of the given name.
If unsuccessful, it will load the given map, and stop with an error if the name does not correspond to either a map or a STRDS

The following raster maps are necessary:
  - Digital elevation model in meters
  - Friction, expressed as Manning's n

The following raster space-time datasets are optional:
  - rain map in mm/h
  - user defined inflow in m/s (vertical velocity, i.e for 20 m3/s on a 10x10 cell, the velocity is 0.2 m/s)
  - boundary condition type: an integer map (see below)
  - boundary condition value: a map for boundary conditions using user-given value

The following informations are needed to start the simulation:
  - the simulation duration could be given by a combination of start_time, end_time and sim_duration.
  If only the duration is given, the results will be written as relative time STRDS
  - record_step: the step in which results maps are written to the disk

## Boundary values
  Only the cells on the edge of the map are used by the module. All other values are ignored
  The boundary type is defined by the following cell values:
  - 1: closed: flow = 0
  - 2: open: z=neighbour, depth=neighbour, v=neighbour
  - 3: fixed_h: z=neighbour,  water surface elevation=user defined, q=variable
  
  The boundary value map is used in the case of type 3 boundary condition

## Output data
The user can choose to output the following:
  - water depth
  - water surface elevation (depth + DEM)

A raster space-time dataset is created for each selected output.
Maps are written using the STRDS name as a prefix.

# Installation
t.sim.flood depends on GRASS GIS 7 and Cython. Numpy is needed but is normally a GRASS dependency.
Copy all the source in the directory of your choice.

Run cython:

$ cython flow.pyx

Compile the generated C file

$ gcc -shared -pthread -fPIC -O3 -Wall -fno-strict-aliasing -fopenmp -I/usr/include/python2.7 -o flow.so flow.c

Launch GRASS

$ grass70

Check usage of the module

$ python t.sim.flood.py --h

# Known issues

  - NULL cells are not handled. Any map containing such cell would lead to the program generating unpredictable results
  - Instabilities may occur in high slopes.
