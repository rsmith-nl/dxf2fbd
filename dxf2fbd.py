#!/usr/bin/env python
# file: dxf2fbd.py
# vim:fileencoding=utf-8:fdm=marker:ft=python
#
# Copyright © 2021 R.F. Smith <rsmith@xs4all.nl>
# SPDX-License-Identifier: MIT
# Created: 2021-06-19T21:37:08+0200
# Last modified: 2023-08-07T19:54:40+0200
"""
Converts lines, lwpolylines, arcs and partial ellipses from the layer named
“contour” in a DXF file to equivalents in an FBD file, suitable for showing
with “cgx -b”.

The XY plane in the dxf file is converted to the YZ plane in the fbd file.
Any Z-coordinates in the dxf file are ignored.

If it finds closed loops of exactly four lines or arcs, it will create
surfaces for them.

The generated output is a starting point for creating and extruding surfaces.
"""

import argparse
import collections as co
import datetime
import itertools as it
import sys
import logging
import os
import math

__version__ = "2023.08.07"
# Default distance within which coordinates are considered identical
EPS = 1e-4
# Default output scaling factor; mm*SCALE → m
SCALE = 0.001


def main(args):
    """
    Entry point for dxf2fbd.py.

    Arguments:
        args (sequence): command-line arguments.
    """
    opts = argparse.ArgumentParser(prog="dxf2fbd", description=__doc__)
    opts.add_argument(
        "-t",
        "--tolerance",
        type=float,
        default=EPS,
        help=f"minimum difference between distinct coordinates (default: {EPS})",
    )
    opts.add_argument(
        "-s",
        "--scale",
        type=float,
        default=SCALE,
        help=f"scaling factor from DXF to CalculiX (default: {SCALE})",
    )
    opts.add_argument("-v", "--version", action="version", version=__version__)
    opts.add_argument(
        "--log",
        default="warning",
        choices=["debug", "info", "warning", "error"],
        help="logging level (defaults to 'warning')",
    )
    opts.add_argument("infile", type=str, help="path to input file")
    opts.add_argument(
        "outfile",
        nargs="?",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="path to output file (default: standard output)",
    )
    args = opts.parse_args(args)
    logging.basicConfig(
        level=getattr(logging, args.log.upper(), None),
        format="# %(levelname)s: %(message)s",
    )
    try:
        points, lines, arcs, splines = load(args.infile, args.tolerance)
    except OSError:
        logging.error(f"cannot open file “{args.infile}”")
        sys.exit(2)
    if len(points) == 0:
        logging.error("no points found")
        sys.exit(3)
    write_fbd(args.outfile, points, lines, arcs, splines, args.infile, args.scale)
    if args.outfile != sys.stdout:
        args.outfile.close()


def load(name, tolerance):  # noqa
    """
    Load the drawing entities from the “contour” layer from a DXF file.

    Arguments:
        name (str): path to the DXF file to load.
        tolerance (float): minimum distance between distinct coordinates.

    Returns:
        points: list of 2-tuples of coordinate strings.
        lines: list of 2-tuples of indices (start, end) into the points list.
        arcs: list of 3-tuples of indices (start, end, center) into the points list.
        splines: list of n-tuples indices (start, end, ...) into the points list.
    """

    def pntidx(item):
        for n, (a, b) in enumerate(points):
            da, db = abs(float(a) - item[0]), abs(float(b) - item[1])
            if da < tolerance and db < tolerance:
                return n
        points.append((item[0], item[1]))
        return len(points) - 1

    ents = entities(parse(name))
    contours = fromlayer(ents, "contour")
    if len(contours) == 0:
        logging.error("no entities in layer “contour”")

    unknown = set(bycode(e, 0) for e in contours) - {
        "ARC",
        "LINE",
        "LWPOLYLINE",
        "ELLIPSE",
    }
    for u in unknown:
        logging.warning(f"entities of type “{u}” will be ignored.")
    points = []  # list of (y,z) coordinates
    lines = []  # list of 2-tuples of indexes into the points list.
    for ln in [e for e in contours if bycode(e, 0) == "LINE"]:
        startidx = pntidx((float(bycode(ln, 10)), float(bycode(ln, 20))))
        endidx = pntidx((float(bycode(ln, 11)), float(bycode(ln, 21))))
        lines.append((startidx, endidx))
    arcs = []
    for arc in [e for e in contours if bycode(e, 0) == "ARC"]:
        center = (float(bycode(arc, 10)), float(bycode(arc, 20)))
        cenidx = pntidx(center)
        radius = bycode(arc, 40)
        radiusf = float(radius)
        startangle = math.radians(float(bycode(arc, 50)))
        endangle = math.radians(float(bycode(arc, 51)))
        startcoord = (
            center[0] + radiusf * math.cos(startangle),
            center[1] + radiusf * math.sin(startangle),
        )
        endcoord = (
            center[0] + radiusf * math.cos(endangle),
            center[1] + radiusf * math.sin(endangle),
        )
        startidx = pntidx(startcoord)
        endidx = pntidx(endcoord)
        arcs.append((startidx, endidx, cenidx))
    for lwp in [e for e in contours if bycode(e, 0) == "LWPOLYLINE"]:
        xvals = (float(j) for j in bycode(lwp, 10))
        yvals = (float(j) for j in bycode(lwp, 20))
        lwpix = [pntidx((x, y)) for x, y in zip(xvals, yvals)]
        for si, ei in zip(lwpix[:-1], lwpix[1:]):
            lines.append((si, ei))
    splines = []
    # We need ≥7 segments in 90° to make a decent elliptical arc.
    segment_angle = math.pi / (2 * 7)
    # Generate splines to represent an elliptical arc.
    for ell in [e for e in contours if bycode(e, 0) == "ELLIPSE"]:
        cx, cy = float(bycode(ell, 10)), float(bycode(ell, 20))
        dx, dy = float(bycode(ell, 11)), float(bycode(ell, 21))
        a = math.sqrt(dx**2 + dy**2)
        cosφ, sinφ = dx / a, dy / a
        b = float(bycode(ell, 40)) * a
        start, end = float(bycode(ell, 41)), float(bycode(ell, 42))
        while start > end:
            end += 2 * math.pi
        arc = end - start
        segments = math.ceil(arc / segment_angle)
        da = arc / segments
        angles = (j * da + start for j in range(segments + 1))
        spoints = ((a * math.cos(t), b * math.sin(t)) for t in angles)
        # transform to global coordinates
        spoints = (
            (x * cosφ - y * sinφ + cx, x * sinφ + y * cosφ + cy) for x, y in spoints
        )
        indices = [pntidx((x, y)) for x, y in spoints]
        print(f"DEBUG: indices = {indices}")
        last = indices[-1]
        indices = indices[:-1]
        indices.insert(1, last)
        splines.append(tuple(indices))
    return points, lines, arcs, splines


def surfaces(lines, arcs, splines):
    """
    Find closed loops of length 3--5.

    Arguments:
        lines: list of 2-tuples of indices (start, end) into the points list.
        arcs: list of 3-tuples of indices (start, end, center) into the points list.
        splines: list of n-tuples indices (start, end, ...) into the points list.

    Returns:
        A list of tuples defining surfaces.
    """
    # geom has to be built up in the same sequence here as lines, arcs and
    # splines are handled below in write_fbd!
    geom = lines + [a[:2] for a in arcs] + [s[:2] for s in splines]
    # find closed loops of 4 entities
    rv = []
    for length in (3, 4, 5):
        for comb in it.combinations(geom, length):
            # Count how often each point occurs
            c = co.Counter(it.chain(*comb))
            # For a closed loop, all points should occur exactly twice.
            if all(j == 2 for j in c.values()):
                rv.append(tuple(geom.index(ln) + 1 for ln in comb))
    return rv


def write_fbd(stream, points, lines, arcs, splines, path, scale): # noqa
    """
    Write the points, lines, arcs and splines to a CalculiX Graphics file.

    Arguments:
        stream: file to write to.
        points: list of 2-tuples of coordinate strings.
        lines: list of 2-tuples of indices (start, end) into the points list.
        arcs: list of 3-tuples of indices (start, end, center) into the points list.
        splines: list of n-tuples indices (start, end, ...) into the points list.
        path: path to the original DXF file.
        scale: factor to scale DXF coordinates with.
    """
    # Header
    stream.write("# Generated by dxf2inp.py" + os.linesep)
    stream.write(f"# from “{path}”" + os.linesep)
    stream.write("# on " + str(datetime.datetime.now())[:-7] + os.linesep)

    stream.write(os.linesep + "# Points extracted from DXF" + os.linesep)
    pprec = math.floor(math.log10(len(points))) + 1
    for n, p in enumerate(points, start=1):
        stream.write(
            f"pnt P{n:0{pprec}d} 0.0 {p[0]*scale:.7f} {p[1]*scale:.7f}" + os.linesep
        )

    lprec = math.floor(math.log10(len(lines) + len(arcs) + len(splines))) + 1

    if lines:
        stream.write(os.linesep + "# Lines extracted from DXF" + os.linesep)
        for n, ln in enumerate(lines, start=1):
            stream.write(
                f"line L{n:0{lprec}d} P{ln[0]+1:0{pprec}d} P{ln[1]+1:0{pprec}d} "
                + os.linesep
            )

    if arcs:
        stream.write(os.linesep + "# Arcs extracted from DXF" + os.linesep)
        for n, ln in enumerate(arcs, start=len(lines) + 1):
            stream.write(
                f"line L{n:0{lprec}d} P{ln[0]+1:0{pprec}d} "
                f"P{ln[1]+1:0{pprec}d} P{ln[2]+1:0{pprec}d} " + os.linesep
            )

    if splines:
        stream.write(os.linesep + "# Ellipes/splines extracted from DXF" + os.linesep)
        for n, sp in enumerate(splines, start=len(lines)+len(arcs)+1):
            cps = [f"P{k+1:0{pprec}d}" for k in sp[2:]]
            sstr = f"seqa S{n:0{lprec}d} pnt " + ' '.join(cps) + os.linesep
            stream.write(sstr)
            stream.write(
                f"line L{n:0{lprec}d} P{sp[0]+1:0{pprec}d} P{sp[1]+1:0{pprec}d} "
                + f"S{n:0{lprec}d}"
                + os.linesep
            )

    surf = surfaces(lines, arcs, splines)
    if surf:
        sprec = math.floor(math.log10(len(surf))) + 1
        stream.write(os.linesep + "# Detected surfaces" + os.linesep)
        for n, s in enumerate(surf, start=1):
            stream.write(f"surf S{n:0{sprec}d}")
            for ln in s:
                stream.write(f" L{ln:0{lprec}d}")
            stream.write(os.linesep)

    # Footer
    stream.write("# End of extracted data." + os.linesep)
    stream.write(os.linesep + "# Show geometry up to now" + os.linesep)
    stream.write("plot pa all" + os.linesep)
    stream.write("plus la all" + os.linesep)
    stream.write("plus sa all" + os.linesep)
    stream.write("rot y" + os.linesep)
    stream.write("rot r 90" + os.linesep)
    stream.write("break" + os.linesep)


def parse(filename):
    """
    Read a DXF file and break it into (group, data) tuples.

    Arguments:
        filename (str): Path to a DXF file to read.

    Returns:
        A list of (group, data) tuples.
    """
    with open(filename, encoding="cp1252") as dxffile:
        lines = dxffile.readlines()
    lines = [ln.strip() for ln in lines]
    data = list(zip(lines[::2], lines[1::2]))
    return [(int(g), d) for g, d in data]


def entities(data):
    """
    Isolate the entity data from a list of (group, data) tuples.

    Arguments:
        data: Input list of DXF (group, data) tuples.

    Returns:
        A list of drawing entities, each as a dictionary
        keyed by group code.
    """
    soe = [n for n, d in enumerate(data) if d[1] == "ENTITIES"][0]
    eoe = [n for n, d in enumerate(data) if d[1] == "ENDSEC" and n > soe][0]
    entdata = data[soe + 1 : eoe]
    idx = [n for n, d in enumerate(entdata) if d[0] == 0] + [len(entdata)]
    pairs = list(zip(idx, idx[1:]))
    # NOTE: don't use a dict for entities! Some entities like LWPOLYLINE
    # have multiple groups 10 and 20.
    entities = [tuple(entdata[b:e]) for b, e in pairs]
    return entities


def bycode(ent, group):
    """
    Get the data with the given group code from an entity.

    Arguments:
        ent: An iterable of (group, data) tuples.
        group: Group code that you want to retrieve.

    Returns:
        The data for the given group code. Can be a list of items if the group
        code occurs multiple times.
    """
    data = [v for k, v in ent if k == group]
    if len(data) == 1:
        return data[0]
    return data


def layername(ent):
    """Get the layer name of an entity."""
    return [v for k, v in ent if k == 8][0]


def fromlayer(entities, name):
    """
    Return only the entities from the named layer.

    Arguments:
        entities: An iterable of dictionaries, each containing a DXF entity.
        name: The name of the layer to filter on.

    Returns:
        A list of entities.
    """
    return [e for e in entities if layername(e) == name]


if __name__ == "__main__":
    main(sys.argv[1:])
