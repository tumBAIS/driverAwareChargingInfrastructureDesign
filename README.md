# DACID tools
DACID = Driver-aware charging infrastructure design

This repository consists of tools for planning and evaluating charging stations for electric vehicles in urban environments.
The code is based on the paper "Driver-aware charging infrastructure design" by Stefan Kober, Maximilian Schiffer, Stephan Sorgatz and Stefan Weltge (2022).

## Requirements
Our tools are written in Python 3 and require the following packages.
Apart from

- standard packages (numpy, scipy, logging, csv, tqdm, ...),

our tools require 

- sortedcontainers

- cdd (for polyhedral computations)

and

- gurobipy (for solving mixed-integer programs)

to be installed.
For the latter package we recommend to install Gurobi's solver (with a free academic license if needed).

## Structure
The provided code consists of two main packages, namely the optimization and the simulation module, as well as a shared data folder.
Example data is provided in `example/`.
The driver, trip, and position data in `example/drivers.csv`, `example/trips.csv`, and `example/positions.csv` has been processed based on MATSim data created by the Transport Systems Planning and Transport Telematics group of Technische Universität Berlin which is available at https://svn.vsp.tu-berlin.de/repos/public-svn/matsim/scenarios/countries/de/duesseldorf.

## Usage
The core of our tools are routines to compute positions of charging stations based on various input such as driver data.
Assuming you cloned our repository into your working directory, these routines can be accessed via

```python
from dacid.interface import optimize
```

To run the optimization, some input data is needed. 
First of all, the possible positions of charging stations must be provided in a csv-file (say "positions.csv") of the form 

```csv
cx,cy
7,23
4,14
13,64
...
```

where each line contains the x,y-coordinates of a possible charging station.
Here, we assume that charging stations are placed in the Euclidean plane.

Second, we need to define drivers in a csv-file (say "drivers.csv") of the form 

```csv
id,home,wallbox,lowerBound
10,c,False,0.2
7825,o,False,0.62381
12,o,True,0.74128
263,r,False,0.5
...
```

where "id" denotes a unique identifier of a driver, "home" specifies the type of starting region (c=city, r=region, o=outer), "wallbox" specifies whether a driver can charge at home (True/False), and "lowerBound" denotes a lower bound on the state of charge before the first trip.

Third, the trips of all drivers must be provided in a csv-file (say "trips.csv") of the form 

```csv
agent,tripId,sx,sy,ex,ey,distance,t_start,t_end,act
10,10_1,351.93,56.94,344.24,56.74,157,39839,45634,leisure
10,10_2,344.24,56.74,347.81,57.85,767,46776,56434,leisure
104,104_1,351.97,566.73,345.95,567.62,145,25829,59340,work
104,104_2,345.95,567.62,351.97,566.73,153,61151,110040,home
...
```

where "agent" denotes the unique identifier of the driver, "tripId" denotes a unique identifier of each trip, "sx,sy,ex,ey" specify the start and end x,y-coordinates of the trip respectively, "distance" specifies the length of the trip, "t_start,t_end" denote the start and end time of the associated break, and "act" denotes the type of activity during the break (which, however, is not exploited in the current version of the optimization, but may be useful for evaluation purposes).

Finally, the user should consider the file `optimization/const.py`, in which several important constants (such as the maximum distance a driver is willing to walk from a charging station to an activity, or a budget on the number of charging stations) are defined and explained.
Optimal charging stations can now be computed via 

```python
optimize("positions.csv", "drivers.csv", "trips.csv", "result.csv")
```

where "result.csv" denotes the name of the file the output is written to.
With this command, the driver data is converted into some combinatorial information about drivers and their stops during a typical day, on which basis a mixed integer program is solved to determine an optimal allocation of charging stations (see our paper for details).
The resulting output is of the form 

```csv
cx,cy,fast,slow,wkt
74,113,4,0,POINT (346372.56 5677352.32)
70,110,0,4,POINT (345972.56 5677052.32)
66,109,0,2,POINT (345572.56 5676952.32)
...
```

where "cx,cy" denote the Euclidean coordinates of the charging stations, "fast,slow" denote the number of fast and slow charging ports respectively, and "wkt" denotes the point of the charging station in well-known text representation (can be used for easy plotting), using the coordinate reference system "EPSG:25832".

An example of this process together with sample data from the city of Düsseldorf can be found in `example.py`.

As the second part of our tools, we offer a simple simulation for assessing the quality of the computed placements, which can be accessed via

```python
from dacid.interface import simulate

simulate("result.csv", "drivers.csv", "trips.csv", "positions.csv")
```

where the input files are as above.
The user should consider the file `simulation/const.py`, which defines several constants used in the simulation.
For details regarding the simulation, please consider our paper.

## Feedback and help
Please feel free to contact us in case you need any help in using our tools. 
More generally, we are happy to receive any feedback regarding our tools.