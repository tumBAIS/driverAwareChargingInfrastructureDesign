import optimization.agentUtils
import optimization.const
import optimization.modelUtils
import optimization.positionUtils

import simulation.const
import simulation.Engine
import simulation.utils

import logging

#main method for creating a model for the base scenario from the data
def optimize(position_file,driver_file,trip_file,result_file):
    #logger settings
    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _LOGGER = logging.getLogger(__name__)
    LOG_LEVEL = logging.DEBUG
    _LOGGER.setLevel(LOG_LEVEL)
    
    #get agents and endpoints
    _LOGGER.info("creating agents")
    size=[0,0]
    e_agents_relevant = optimization.agentUtils.createEAgents(optimization.const.SEED,optimization.const.E_QUOTA,trip_file,driver_file,size=size)
    breakpoints = set()
    for agent in e_agents_relevant.values():
        for stop in agent.schedule:
            breakpoints.add((float(stop["sx"]),float(stop["sy"])))

    #get potential locations
    _LOGGER.info("calculating possible locations")
    innerCells = optimization.positionUtils.findAllCells(position_file)
    reducedCells = optimization.positionUtils.filterCells(innerCells,breakpoints,radius=optimization.const.WALKING_RADIUS)
    relevantCellsPerBreakpoint = optimization.positionUtils.findRelevantCellsForBreakpoints(breakpoints,reducedCells)
    relevantBreakpoints = {key:"f" for key,val in relevantCellsPerBreakpoint.items() if len(val)>0}

    #get patterns
    _LOGGER.info("calculating possible charging patterns")
    unsat_agents = []
    for key,agent in e_agents_relevant.items():
        agent.calculatePatterns(relevantBreakpoints)
        if not agent.valid_patterns:
            c = 0
            for opp in agent.charging_opps:
                if opp["loc"] in relevantBreakpoints:
                    c+=1
            if c<4:   
                unsat_agents.append(key)
    if unsat_agents:
        _LOGGER.warning(f"removing {len(unsat_agents)} agents with less than 4 charging opportunities that have no valid schedule!",Warning)
        for key in unsat_agents:
            del e_agents_relevant[key]

    #create model
    _LOGGER.info("creating model")
    m = optimization.modelUtils.csBaseModel(
        e_agents_relevant,
        reducedCells,
        relevantCellsPerBreakpoint,
        relevantBreakpoints
        )
    m.addStandardConstraints()
    m.addCSObjective()

    m.optimize()

    m.logSolutionStatistics()

    m.saveSolutionToFile(result_file)
    return

def simulate(result_file,driver_file,trip_file,position_file):

    LOG_LEVEL = logging.WARNING

    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=LOG_LEVEL,
    )

    # generate random day
    day = simulation.utils.generate_day(driver_file, trip_file, simulation.const.SEED, simulation.const.E_QUOTA)

    # run simulation
    charging_stations = simulation.utils.read_charging_stations(result_file)
    inner_cells = simulation.utils.read_cells(position_file)
    engine = simulation.Engine.SimulationEngine(day, charging_stations, inner_cells, simulation.const.RADIUS_HAPPY, simulation.const.RADIUS_MAX)
    engine.simulate(warm_start = simulation.const.WARM_START)
    result = engine

    # analyze behavior
    print(result.num_successful_agents, "/", result.num_relevant_agents)
    print(result.get_happy_quota(groundset="demand"))
    print(result.num_total_agents)
    print(result.num_relevant_agents)
    print(len(result.totally_failed_agents))

    return