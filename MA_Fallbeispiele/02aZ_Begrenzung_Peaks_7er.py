"""
Analog zu 02a, aber explizite Gegenüberstellung der Fälle mit Lastspitzenreduktion (LSR) und ohne,
demnach insg. 7 Fälle
"""
import json
import os

from h2pp.optimizer import optimize_h2pp

import commonFunctions as h2ppcf


def siebener_analyse(datapath, file_path, exp_name, ev_usage_on_weekends=True):
    h2ppcf.create_export_folder(exp_name)

    # Prepare EV json
    ev_tempfile_path = os.path.join(datapath,
                                    "TEMPFILE_ONLY__config_ev.json")  # must be in this folder so that the relative path in the json file still works
    h2ppcf.switch_fcev_with_ev(input_file_path=file_path,
                               output_file_path=ev_tempfile_path, usage_on_weekends=ev_usage_on_weekends)

    # ====  ====
    tco_normal, figs = optimize_h2pp(file_path, mode="normal") # 1. Campus + H2PP + FCEV
    tco_battery_fcev, figs = optimize_h2pp(file_path, mode="battery_ref") # 2. Campus + Battery + FCEV
    tco_battery_bev, figs = optimize_h2pp(ev_tempfile_path, mode="battery_ref") # 3. Campus + Battery + BEV
    tco_sq_fcev, figs = optimize_h2pp(file_path, mode="power_grid_only_ref") # 4. Campus + FCEV (no H2PP or Batt.)
    tco_sq_bev, figs = optimize_h2pp(ev_tempfile_path, mode="power_grid_only_ref") # 5. Campus + EV (no H2PP or Batt.)

    # strombezug begrenzen beim Battery_FCEV und Battery_BEV:
    with open(ev_tempfile_path) as user_file:
        config_dict_sb_ev = json.load(user_file)

    config_dict_sb_ev['strombezug_begrenzen'] = True
    file_path_sb_ev = os.path.join(datapath, '_temp_file_begrenzung_sb_X01.json')  # may NOT exist or will be overwritten
    with open(file_path_sb_ev, "w") as user_file:
        json.dump(config_dict_sb_ev, user_file, indent=4)

    tco_sb_ev, figs = optimize_h2pp(file_path_sb_ev, mode="battery_ref") # 6. Campus + Battery + BEV + Lastspitzenreduktion

    # strombezug begrenzung für FCEV Battery:
    with open(file_path) as user_file:
        config_dict_sb_fcev = json.load(user_file)

    config_dict_sb_fcev['strombezug_begrenzen'] = True
    file_path_sb_fcev = os.path.join(datapath, '_temp_file_begrenzung_sb_X02.json')  # may NOT exist or will be overwritten
    with open(file_path_sb_fcev, "w") as user_file:
        json.dump(config_dict_sb_fcev, user_file, indent=4)

    tco_sb_fcev, figs = optimize_h2pp(file_path_sb_fcev, mode="battery_ref") # 7. Campus + Battery + FCEV + Lastspitzenreduktion



    labels = ["H2PP", "Batt. (FCEV)", "Batt. (FCEV) + LSR", "Batt. (EV)", "Batt. (EV) + LSR", "Only Grid (FCEV)", "Only Grid (EV)"]
    tcos = [tco_normal, tco_battery_fcev, tco_sb_fcev, tco_battery_bev, tco_sb_ev
            , tco_sq_fcev, tco_sq_bev]

    h2ppcf.multiple_tco_costs_and_revenue_bars_export(exp_name, tcos, labels)
    h2ppcf.multiple_tco_total_cost_comparison_export(exp_name, tcos, labels)

    # Delete our temporary EV json file
    os.remove(ev_tempfile_path)

datapath = os.path.join(os.path.dirname(__file__), "Fallstudie Exemplarisches Industrieareal")
file_path = os.path.join(datapath, "config_microgrid.json")

# Bevor IRGENDWAS MODIFIZIERT WIRD, muss ich die  7ers testen, sonst hab ich Lastspitzenglättung schon überall realisiert!!
# siebener Analyse!! MIT Lastglätung PLUS .
siebener_analyse(datapath, file_path, "Exp_02A_7ers")


