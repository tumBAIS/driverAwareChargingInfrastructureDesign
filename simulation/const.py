#global constants
SEC_PER_DAY = 24*60*60  #number of seconds in 24 hours

#instance setup
SEED = 68352    #seed for random representative day generation
E_QUOTA = 0.02  #proportion of drivers with ev
WARM_START = 5

#ev settings
CSPEED_SLOW = 11        #charging speed for slow charging stations
EFFICIENCY_SLOW = .85   #efficiency for slow charging stations
EFFCSPEED_SLOW = CSPEED_SLOW * EFFICIENCY_SLOW  #effective charging speed for slow charging stations
MIN_CHARGE = .1     #min soc throughout the day
MIN_CHARGE_EOD = .1     #min soc when arriving at the end of the day
MAX_EXACT_STOPS = 3     #maximum number of stops for exact pattern calculation (beware of memory and runtime issues when increasing)
RADIUS_HAPPY = 400      #radius, drivers are happy to walk between charging station and place of activity
RADIUS_MAX = 5000       #radius, drivers will travel in the worst case between charging station and place of activity
TOT_CAP = 50    #capacity of the battery. Current possible values: 50; need to add range and charging curves for other capacities
if TOT_CAP == 50:
    TOT_RANGE = 260     #total range of the ev
else:
    raise ValueError(f"unknown value {TOT_CAP} for TOT_CAP")

#city settings
CITY = "duesseldorf"            #city to be evaluated. Currently only duesseldorf is possible. For further cities, please provide own data and add the following constants 
if CITY == "duesseldorf":
    MIN_X = 338635.69591432833      #bounding box around the city for coordinate transformation to 100m Euclidean projection
    MIN_Y = 5665755.031875165      #bounding box around the city for coordinate transformation to 100m Euclidean projection
    MAX_X = 356301.22167132614      #bounding box around the city for coordinate transformation to 100m Euclidean projection
    MAX_Y = 5691431.235557389      #bounding box around the city for coordinate transformation to 100m Euclidean projection

    CELL_TYPES = ["City"]           #different types of regions (if city has surrounding region that is relevant for planning, add "Region")

    TOT_AGENTS = 512236             #total number of drivers to sample from
    if TOT_CAP == 50:
        O_QUOTA = 74114/100854      #total number of drivers coming from outside the planning area
    else:
        raise ValueError(f"unknown value {TOT_CAP} for TOT_CAP")