#!/usr/bin/env python

import sys
import argparse

import pysam

from ragoo2_utilities.utilities import reverse_complement


def log_err(n, s):
    s = "line " + str(n) + ": " + s
    raise RuntimeError(s)


def is_covered(s):
    s = sorted(s)
    for j in range(1, len(s)):
        if s[j-1][1] != s[j][0]:
            return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Build sequences in FASTA format from an AGP v2.1 file. ")
    parser.add_argument("agp", metavar="<scaffolds.agp>", type=str, help="AGP v2.1 file")
    parser.add_argument("components", metavar="<components.fasta>", type=str, help="FASTA file with component sequences to be scaffolded. must not be gzipped")

    args = parser.parse_args()
    agp_file = args.agp
    components_file = args.components

    fai = pysam.FastaFile(components_file)
    line_number = 0
    prev_pid = 0
    curr_obj = None
    seen_objs = set()
    curr_obj_intervals = []
    past_comments = False
    is_first = True
    allowed_comp_types = {"A", "D", "F", "G", "O", "P", "W", "N", "U"}
    allowed_linkage_types = {"yes", "no"}
    allowed_gap_types = {
        "scaffold",
        "contig",
        "centromere",
        "short_arm",
        "heterochromatin",
        "telomere",
        "repeat",
        "contamination"
    }
    allowed_evidence_types = {
        "na",
        "paired-ends",
        "align_genus",
        "align_xgenus",
        "align_trnscpt",
        "within_clone",
        "clone_contig",
        "map",
        "pcr",
        "proximity_ligation",
        "strobe",
        "unspecified"
    }

    # Iterate over the lines of the AGP file
    with open(agp_file, "r") as f:
        for line in f:
            line_number += 1

            # Deal with the headers
            if line.startswith("#"):
                if past_comments:
                    log_err(line_number, "illegal comment in AGP body")
            else:
                # This is an AGP body line
                past_comments = True
                fields = line.rstrip().split("\t")

                # There should be exactly 9 tab delimited fields
                if not len(fields) == 9:
                    log_err(line_number, "lines should have 9 tab delimited fields")

                # All fields should have a value
                if not all(fields):
                    log_err(line_number, "detected empty field")

                # Object specific operations
                obj, obj_beg, obj_end = fields[0], int(fields[1]), int(fields[2])
                obj_len = obj_end - (obj_beg - 1)
                pid = int(fields[3])

                if obj_beg < 1 or obj_end < 1:
                    log_err(line_number, "object coordinates should be 1-indexed and positive")

                if obj_beg > obj_end:
                    log_err(line_number, "beginning object coordinate should be <= the end coordinate")

                # Check if we are transitioning object identifiers
                if obj != curr_obj:

                    # Make sure we start at the beginning coordinate
                    if not obj_beg == 1:
                        log_err(line_number, "all objects should start with '1'")

                    # Ensure we have not yet seen this object identifier
                    if obj in seen_objs:
                        log_err(line_number, "object identifier out of order")

                    # Check that the last object has been completely covered
                    if not is_first:
                        if not is_covered(curr_obj_intervals):
                            log_err(line_number, "some positions in %s are not accounted for or overlap" % curr_obj)

                    # Write the fasta header for the object
                    header = ">" + obj + "\n"
                    if not is_first:
                        header = "\n" + header
                    sys.stdout.write(header)

                    # Update all the info for this new object
                    prev_pid = 0
                    seen_objs.add(obj)
                    curr_obj = obj
                    curr_obj_intervals = []
                    is_first = False

                if pid - prev_pid != 1:
                    log_err(line_number, "non-sequential part_numbers")

                prev_pid = pid
                curr_obj_intervals.append((obj_beg-1, obj_end))

                # The remaining operations depends on if this line is a gap or not.
                comp_type = fields[4]
                if comp_type not in allowed_comp_types:
                    log_err(line_number, "invalid component type: %s" % comp_type)

                if comp_type != "N" and comp_type != "U":
                    # This is a sequence component
                    cid, comp_beg, comp_end = fields[5], int(fields[6]), int(fields[7])

                    if comp_beg < 1 or comp_end < 1:
                        log_err(line_number, "component coordinates should be 1-indexed and positive")

                    if comp_beg > comp_end:
                        log_err(line_number, "beginning component coordinate should be less than or equal to the end coordinate")

                    comp_len = comp_end - (comp_beg - 1)
                    orientation = fields[8]

                    # Write the fasta sequence for this component
                    if orientation in {"+", "?", "0", "na"}:
                        sys.stdout.write(fai.fetch(cid))
                    elif orientation == "-":
                        sys.stdout.write(reverse_complement(fai.fetch(cid)))
                    else:
                        log_err(line_number, "invalid orientation")
                else:
                    # This is a gap component
                    comp_len, gap_type, linkage, evidence = int(fields[5]), fields[6], fields[7], fields[8]

                    # Check if this is a valid gap type
                    if gap_type not in allowed_gap_types:
                        log_err(line_number, "invalid gap type")

                    if linkage not in allowed_linkage_types:
                        log_err(line_number, "invalid linkage field")

                    if comp_len < 1:
                        log_err(line_number, "gap length must be >0")

                    if comp_type == "U" and comp_len != 100:
                        log_err(line_number, "gaps of type 'U' must be 100 bp")

                    # Check for valid evidence
                    all_evidence = evidence.split(";")
                    for e in all_evidence:
                        if e not in allowed_evidence_types:
                            log_err(line_number, "invalid linkage evidence")

                    # Write the gap sequence to the fasta file
                    sys.stdout.write("N"*comp_len)

                # Ensure that the coordinates indicate the same length in the object and component
                if comp_len != obj_len:
                    log_err(line_number, "object and component coordinates have inconsistent lengths")

    sys.stdout.write("\n")


if __name__ == "__main__":
    main()