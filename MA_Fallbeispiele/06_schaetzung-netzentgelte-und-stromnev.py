"""
MA p. 131f.: Analyse der Güte der Schätzung von Netzentgelten und Strom-NEV-Mittelung
"""

import json
import os
import commonFunctions as h2ppcf
from h2pp.optimizer import optimize_h2pp

datapath = os.path.join(os.path.dirname(__file__), "Fallstudie Exemplarisches Industrieareal")
file_path = os.path.join(datapath, "config_microgrid.json")

# Prepare EV json

ev_tempfile_path = os.path.join(datapath,
                                "TEMPFILE_ONLY__config_ev.json")  # must be in this folder so that the relative path in the json file still works
h2ppcf.switch_fcev_with_ev(input_file_path=file_path,
                           output_file_path=ev_tempfile_path, usage_on_weekends=True)
# ==== 1. Campus + H2PP + FCEV ====
print("STARTING WITH H2PP+FCEV!")
tco_normal, figs = optimize_h2pp(file_path, mode="normal", verbose=True)
# export_jahreszeiten_und_stacked_tco_plot(tco_normal, figs, exp_name, "H2PP_FCEV")


# ==== 2. Campus + Battery + BEV ====
print("STARTING WITH BATTERY+BEV!")
tco_battery_bev, figs = optimize_h2pp(ev_tempfile_path, mode="battery_ref", verbose=True)
# export_jahreszeiten_und_stacked_tco_plot(tco_battery_bev, figs, exp_name, "Batt_BEV")


# ==== 3. Campus + Battery + BEV + Lastspitzenreduktion ====
print("STARTING WITH BATTERY+BEV+PEAK SHAVING!")
with open(ev_tempfile_path) as user_file: # hier direkt die angepasste EV file benutzt von oben
    config_dict = json.load(user_file)

# Deaktiveren der Peaks
config_dict['strombezug_begrenzen'] = True

file_path_out = os.path.join(datapath, '_temp_file_begrenzung_sb.json')  # may NOT exist or will be overwritten
with open(file_path_out, "w") as user_file:
    json.dump(config_dict, user_file, indent=4)

# Das ist unsere neue Base:
file_path = file_path_out
tco_peakshaving_ev, figs = optimize_h2pp(file_path, mode="battery_ref", verbose=True)