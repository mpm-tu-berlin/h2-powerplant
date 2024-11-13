
from scipy.datasets import electrocardiogram
from h2pp.helperFunctions import get_max_depth
import numpy as np

# x = electrocardiogram()[2000:4000]
#x = electrocardiogram()[1500:3500]
#res = get_max_depth(x, plot_peaks=True)
#print(res)


get_max_depth(np.array([0,0,-10,-20, 10]), plot_peaks=True) # const am anfang dann abfall
get_max_depth(np.array([0,0,10,20,20]), plot_peaks=True) # const am anfang dann anstieg, am ende wieder konst
get_max_depth(np.array([10,9,8,7, 6]), plot_peaks=True) # nur abfallen
get_max_depth(np.array([4,5,6,7]), plot_peaks=True) #nur ansteigen
get_max_depth(np.array([4,5,6,7,6,5,4]), plot_peaks=True) # nur HP ohne TP
get_max_depth(np.array([5,4,3,4,5,6]), plot_peaks=True) # nur TP ohne HP
get_max_depth(np.array([1,1,1]), plot_peaks=True) # alle konstant
get_max_depth(np.array([1,1,1,1,1,2,1,1]), plot_peaks=True) # nur ein wert nicht konst
get_max_depth(np.array([1,1,1,1,1,2,2,2]), plot_peaks=True)
get_max_depth(np.array([2,2,1]), plot_peaks=True)
get_max_depth(np.array([2,1]), plot_peaks=True)