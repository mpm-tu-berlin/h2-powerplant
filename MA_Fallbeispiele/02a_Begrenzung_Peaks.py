"""
Chap 6.2.1 (p. 125-129): Testing peak reduction
Test the experimental Peak reduction on the example area.
Setzt den Parameter strombezug_begrenzen im Parameter-Dictionary auf True und simuliert erneut wie in Exp. 01
die fünf Vergleichsszenarien.


"""

import json
import os


import commonFunctions as h2ppcf

datapath = os.path.join(os.path.dirname(__file__), "Fallstudie Exemplarisches Industrieareal")
file_path = os.path.join(datapath, "config_microgrid.json")

with open(file_path) as user_file:
    config_dict = json.load(user_file)

# Deaktiveren der Peaks
config_dict['strombezug_begrenzen'] = True

file_path_out = os.path.join(datapath, '_temp_file_begrenzung_sb.json')  # may NOT exist or will be overwritten
with open(file_path_out, "w") as user_file:
    json.dump(config_dict, user_file, indent=4)

# Das ist unsere neue Base:
file_path = file_path_out


####################################################################

h2ppcf.fuenffach_analyse(datapath, file_path, "Exp_02A")
