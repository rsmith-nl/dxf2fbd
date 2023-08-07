Converting DXF sketches to CalculiX FBD format
##############################################

:date: 2023-08-07
:tags: CalculiX, DXF
:author: Roland Smith

.. Last modified: 2023-08-07T21:46:30+0200
.. vim:spelllang=en

Introduction
============

The author regularly creates extrusions (using “swep”) in CalculiX Graphics.
Doing this manually is a relatively time-consuming process.

For a non-parametric part, it is easier to sketch the geometry in a 2D CAD
program like LibreCAD_, and then convert that sketch to instructions for
CalculiX Graphics.

.. _LibreCAD: https://librecad.org/

This is what ``dxf2fbd.py`` does.

.. PELICAN_END_SUMMARY

What it does
============

It looks in the layer named “contour” in the DXF files, and extracts LINE,
ARC, LWPOLYLINE and ELLIPSE entities. *Other entities and layers are ignored.*
Note that for now, it only handles partial (open) ellipses.

It outputs CalculiX Graphics commands for creating these points, lines and
arcs.
The XY plane in the DXF file is thereby converted in the YZ plane in CalculiX.
*Any Z values in the DXF entities are ignored*.

The distance between coordinates that should not be considered identical in
set in the global ``EPS`` value.
The scaling factor for point coordinates is set in the global ``SCALE`` value.
Currently it is set to convert millimeters in DXF to meters in CalculiX.

The program looks for sets of 3--5 lines that form a closed loop.
Those will be defined as surfaces.


What it doesn't do
==================

* Set line divisions
* Make line combinations
* Create sets

In the view of the author, these are best left to the operator.
When creating a DXF file, the operator should keep the properties of surfaces
in CalculiX graphics in mind when creating them.


Requirements
============

This program should run on Python 3.6 or later.
It has no library requirements outside of the Python standard library.
This version has been developed and tested using Python 3.9.


Installation
------------

To install it for the local user, run::

    python setup.py install

This will install it in the user path for Python scripts.
For POSIX operating systems this is usually ``~/.local/bin``.
For ms-windows this is the ``Scripts`` directory of your Python installation
or another local directory.
Make sure that this directory is in your ``$PATH`` environment variable.
