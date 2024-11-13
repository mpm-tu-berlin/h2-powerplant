"""
Test des Programms zur Analyse der technischen Machbarkeit:
- Für die Fallstudie "Exemplarisches Industrieareal" und "EUREF Campus Duesseldorf" wird die technische Machbarkeit jeweils untersucht
- Es wird die nötige Leistung der Brennstoffzelle und vorrätig zu haltende Wasserstoffmenge untersucht, um einen
 Stromausfall von fester Länge (einmal für 24 Stunden, einmal für 60 Minuten Dauer), aber bei beliebigem Beginn innerhalb der Woche zu überbrücken.
- Außerdem wird untersucht, wie sich diese Werte in Abhängigkeit der Ausfallzeit verhalten.
"""

import os
from commonFunctions import create_export_folder
from h2pp.technische_machbarkeit import plot_fc_power_and_tank_mass, blackout_check, blackout_check_multi_plot

# Disable MathJax for Kaleido so that we will not get the "loading MathJax..." message on our PDF exports
import plotly.io as pio
pio.kaleido.scope.mathjax = None


exp_name = "Exp_05"
create_export_folder(exp_name)

# Fallstudie Exemplarisches Industrieareal
datapath = os.path.join(os.path.dirname(__file__), "Fallstudie Exemplarisches Industrieareal")
file_path = os.path.join(datapath, "config_microgrid.json")

wt = 1380
wt_48h = 1000
ht = 580

#plot_fc_power_and_tank_mass(24 * 60, file_path).show()
plot_fc_power_and_tank_mass(24 * 60, file_path,
                            include_title=False).write_image(f"Plot_Results_For_MA/{exp_name}/"
                                                             f"Exempl_Industrieareal_24hrs_FC_Tank.pdf", width=wt, height=ht)



#plot_fc_power_and_tank_mass(60, file_path).show()
plot_fc_power_and_tank_mass(60, file_path, include_title=False).write_image(f"Plot_Results_For_MA/{exp_name}/"
                                                             f"Exempl_Industrieareal_60min_FC_Tank.pdf", width=wt, height=ht)


fig, plt = blackout_check_multi_plot(file_path, "Exemplarisches Industrieareal")
fig.show()
fig.update_layout(title=None)
fig.write_image(f"Plot_Results_For_MA/{exp_name}/Exempl_Industrieareal_Multi_Plot.pdf", width=wt_48h, height=ht)
plt.savefig(f"Plot_Results_For_MA/{exp_name}/Exempl_Industrieareal_Tankmasse.pdf", dpi=300)
plt.close()


# Fallstudie EUREF Duesseldorf

datapath2 = os.path.join(os.path.dirname(__file__), "Fallstudie EUREF Duesseldorf")
file_path2 = os.path.join(datapath2, "generated_ts_config_euref_dus.json")


#plot_fc_power_and_tank_mass(60, file_path2).show()
plot_fc_power_and_tank_mass(60, file_path2, include_title=False).write_image(f"Plot_Results_For_MA/{exp_name}/"
                                                             f"EUREF_60min_FC_Tank.pdf", width=1380, height=580)


#plot_fc_power_and_tank_mass(24*60, file_path2).show()
plot_fc_power_and_tank_mass(24*60, file_path2, include_title=False).write_image(f"Plot_Results_For_MA/{exp_name}/"
                                                             f"EUREF_24hrs_FC_Tank.pdf", width=1380, height=580)


fig, plt = blackout_check_multi_plot(file_path2, "EUREF Campus Duesseldorf")
fig.show()
fig.update_layout(title=None)
fig.write_image(f"Plot_Results_For_MA/{exp_name}/EUREF_Multi_Plot.pdf", width=wt_48h, height=ht)
plt.savefig(f"Plot_Results_For_MA/{exp_name}/EUREF_Tankmasse.pdf", dpi=300)
plt.close()



