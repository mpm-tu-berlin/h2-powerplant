"""
Simuliert die fünf Vergleichsszenarien für die Fallstudie EUREF Düsseldorf.
"""


from h2pp.optimizer import optimize_h2pp
import commonFunctions as h2ppcf

# Base JSON:
the_json_filename = "generated_ts_config_euref_dus.json"
# generated_ts_config_euref_dus.json # input_dus.json

exp_name = "Exp_03A"

import os
# Basic Simulation
# Achtung, geänderte Annahmen, siehe MA.. Vor allem jetzt auch am WE keine Fahrzeugbetankungen mehr..
datapath = os.path.join(os.path.dirname(__file__), "Fallstudie EUREF Duesseldorf")
file_path = os.path.join(datapath, the_json_filename)

tco_normal, figs = optimize_h2pp(file_path, mode="normal")
tco_normal.plot_stacked_bar_over_period().show()
figs["SOMMER"].show()
figs["UEBERGANG"].show()
figs["WINTER"].show()

####

h2ppcf.fuenffach_analyse(datapath, file_path, exp_name, ev_usage_on_weekends=False)

###
