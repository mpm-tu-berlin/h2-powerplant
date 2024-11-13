"""
Beispielskript zur Simulation und Kostenberechnung für ein exemplarisches Industrieareal mit gegebenen Anlagenparametern (siehe JSON File).
"""

from h2pp.optimizer import optimize_h2pp

if __name__ == '__main__':

    import os
    datapath = os.path.join(os.path.dirname(__file__), "MA_Fallbeispiele", "Fallstudie Exemplarisches Industrieareal")
    file_path = os.path.join(datapath, "config_microgrid.json")

    # mode == "normal" ist der H2PP Fall (andere Möglichkeiten existieren hier für Batterie-Referenz und
    # Power-Grid-Only, siehe Implementierung der optimize_h2pp Funktion)
    tco_normal, figs = optimize_h2pp(file_path, mode="normal")
    tco_normal.plot_stacked_bar_over_period().show()
    figs["SOMMER"].show()
    figs["UEBERGANG"].show()
    figs["WINTER"].show()

    exit(0)
