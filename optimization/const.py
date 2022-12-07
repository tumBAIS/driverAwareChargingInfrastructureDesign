#global constants
SEC_PER_DAY = 24*60*60  #number of seconds in 24 hours      

#instance setup
SEED = 72359    #seed for random representative day generation                        
E_QUOTA = 0.03  #proportion of drivers with ev

#ev settings
CSPEED_SLOW = 11    #charging speed for slow charging stations
EFF_SLOW = .85      #efficiency for slow charging stations
EFFCSPEED_SLOW = CSPEED_SLOW * EFF_SLOW     #effective charging speed for slow charging stations
MIN_CHARGE = .1     #min soc throughout the day
MIN_CHARGE_EOD = .1     #min soc when arriving at the end of the day
WALKING_RADIUS = 200    #radius, drivers walk between charging station and place of activity
TOT_CAP = 50    #capacity of the battery. Current possible values: 50; need to add range and charging curves for other capacities
if TOT_CAP == 50:
    TOT_RANGE = 260     #total range of the ev
else:
    raise ValueError(f"unknown value {TOT_CAP} for TOT_CAP")

#cs settings
COST_FAST = 2       #cost of 1 fast charging port
COST_SLOW = 1       #cost of 1 slow charging port
CONF_FAST = [4,6,8]     #possible port configurations of fast charging stations
CONF_SLOW = [2,4,6,8]   #possible port configurations of slow charging stations

#model settings
B_BUDGET = True     #boolean whether the model has a budget constraint
BUDGET = 400        #value of the budget constraint
B_LIMIT = False     #boolean whether the model has limits on the amount of fast and slow charging stations respectively
LIMIT = (0,0)       #limits for the fast and slow charging stations respectively
B_PROPORTION = False    #boolean whether a certain proportion of drivers needs to be satisfied
PROPORTION = 1.0        #proportion that needs to be satisfied

#model improvements
CAPACITY_CUTS = True    #boolean whether capacity cuts are to be added
FRACTIONAL_ASSIGNMENT = True    #boolean whether the assignment of drivers to charging stations can be fractional
OUTER_DESCRIPTION = True    #boolean whether the outer description of charging demand is to be used

#technical model settings
LOG_FILE = ""       #log file (empty for no log)
METHOD = 1          #lp method (see gurobi docs for specification)
MIPGAP = 0.01       #mipgap (see gurobi docs for specification)
POLYTOPE_THREADS = 6    #number of threads for calculating outer description using cdd
PRESOLVE = True     #presolve (see gurobi docs for specification)
TIMELIMIT = 0       #timelimit (see gurobi docs for specification, 0 for no time limit)

#city settings
CITY = "duesseldorf"        #city to be optimized. Currently only duesseldorf is possible. For further cities, please provide own data and add the following constants
if CITY == "duesseldorf":
    MIN_X = 338635.69591432833      #bounding box around the city for coordinate transformation to 100m Euclidean projection
    MIN_Y = 5665755.031875165       #bounding box around the city for coordinate transformation to 100m Euclidean projection
    MAX_X = 356301.22167132614      #bounding box around the city for coordinate transformation to 100m Euclidean projection
    MAX_Y = 5691431.235557389       #bounding box around the city for coordinate transformation to 100m Euclidean projection

    CELL_TYPES = ["City"]           #different types of regions (if city has surrounding region that is relevant for planning, add "Region")

    TOT_AGENTS = 512236             #total number of drivers to sample from
    if TOT_CAP == 50:
        O_QUOTA = 74114/100854      #total number of drivers coming from outside the planning area
    else:
        raise ValueError(f"unknown value {TOT_CAP} for TOT_CAP")