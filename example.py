from interface import optimize, simulate

#recall to set specific settings in optimization/const.py (in particular model and instance settings)
optimize("example/positions.csv",   #planning area in transformed coordinates based on the region of Düsseldorf
                                    #based on https://svn.vsp.tu-berlin.de/repos/public-svn/matsim/scenarios/countries/de/duesseldorf/duesseldorf-v1.0/original-data/duesseldorf-area-shp/
                                    #coordinates can be transformed to epsg:25832 by (x,y)=(min_x+100*cx,min_y+100*cy)
         "example/drivers.csv",     #attributes for each driver in our planning set
                                    #based on https://svn.vsp.tu-berlin.de/repos/public-svn/matsim/scenarios/countries/de/duesseldorf/projects/komodnext/website/v1.5/base/
                                    #home was chosen based on the start of the first trip in combination with the area of Düsseldorf
                                    #drivers with access to wallboxes were drawn independently at random
                                    #the lower bound on the soc was calculated with respects to the bounds presented in our paper
         "example/trips.csv",       #trips for each driver in our planning set
                                    #based on/processed from https://svn.vsp.tu-berlin.de/repos/public-svn/matsim/scenarios/countries/de/duesseldorf/projects/komodnext/website/v1.5/base/
         "example/result.csv")      #result file (folder should exist, file will be created/overwritten)

#recall to set specific settings in simulation/const.py (in particular instance settings)
simulate("example/result.csv",      #output frome above
         "example/drivers.csv",     #same input as above
         "example/trips.csv",       #same input as above
         "example/positions.csv")   #same input as above (for deciding which charging plans are reasonable)