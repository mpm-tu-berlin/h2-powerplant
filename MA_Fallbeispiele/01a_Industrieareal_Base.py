"""
Simulation und Gegenüberstellung von fünf Szenarien bzw. Anwendungsfällen:
- H2PP
- Grid Only (EV)
- Grid Only (FCEV)
- Batterie (EV)
- Batterie (FCEV)

Details siehe Masterarbeit JC Kapitel 6.1 S. 116-119

Ergebnisse (Plots) werden in einem Unterordner "Exp_01" gespeichert.

"""

import os
import commonFunctions as h2ppcf

datapath = os.path.join(os.path.dirname(__file__), "Fallstudie Exemplarisches Industrieareal")
file_path = os.path.join(datapath, "config_microgrid.json")

h2ppcf.fuenffach_analyse(datapath, file_path, "Exp_01")
