"""
MA Exp. 6.2.2 (p. 129-131):
In diesem Experiment werden Netzentgelte usw. komplett deaktiviert, das heißt der Kaufpreis für Strom entspricht
jetzt dem Verkaufspreis (abzüglich des kleinen festgelegten Abzugbetrags beim Verkauf von 0,184 ct/kWh)

Dann wird erneut die Simulation der fünf Vergleichsszenarien durchgeführt.
"""

import json
import os

import commonFunctions as h2ppcf

datapath = os.path.join(os.path.dirname(__file__), "Fallstudie Exemplarisches Industrieareal")
file_path = os.path.join(datapath, "config_microgrid.json")

with open(file_path) as user_file:
    config_dict = json.load(user_file)

# Deaktiveren der Peaks
config_dict['nur_beschaffungskosten'] = True

file_path_out = os.path.join(datapath, '_temp_file_begrenzung_sb.json')  # may NOT exist or will be overwritten
with open(file_path_out, "w") as user_file:
    json.dump(config_dict, user_file, indent=4)

# Das ist unsere neue Base:
file_path = file_path_out


####################################################################

h2ppcf.fuenffach_analyse(datapath, file_path, "Exp_02B")
