import csv
import logging

import numpy as np

from .Agent import Agent
from .const import MIN_X, MIN_Y, O_QUOTA, TOT_AGENTS

_LOGGER = logging.getLogger(__name__)


def point_to_cell(x, y):
    return (int((x - MIN_X) / 100), int((y - MIN_Y) / 100))


def cell_to_point(x, y):
    return (MIN_X + 100 * (x + 0.5), MIN_Y + 100 * (y + 0.5))


def primary_strategy(vps):
    return sorted(vps, key=weigh_index_sum)[0]


# prefer early breaks
def weigh_index_sum(strat):
    return sum([index for index, i in enumerate(strat) if i > 0])


def create_agents(
    agents_attributes_file,
    agents_schedules_file,
    seed,
    e_quota,
    multi=False,
    size=[0, 0],
):
    rng = np.random.default_rng(seed)

    attribute_dict = dict()
    attributes = csv.DictReader(open(agents_attributes_file, "r"))

    o_agents = list()  # outer agents
    wb_agents = list()  # agents with wallbox
    nwb_agents = list()  # agents without wallbox

    for a in attributes:
        attribute_dict[a["id"]] = a
        if a["home"] == "o":
            o_agents.append(a["id"])
        elif a["wallbox"] == "True":
            wb_agents.append(a["id"])
        else:
            nwb_agents.append(a["id"])

    schedule_dict = dict()
    stops = csv.DictReader(open(agents_schedules_file, "r"))
    for s in stops:
        if s["agent"] in schedule_dict:
            schedule_dict[s["agent"]].append(s)
        else:
            schedule_dict[s["agent"]] = [s]

    num_agents = round(TOT_AGENTS * e_quota)
    num_outer_agents = round(O_QUOTA * num_agents)
    num_inner_agents = num_agents - num_outer_agents

    e_agent_keys = rng.choice(o_agents, num_outer_agents, replace=False)
    e_agent_keys = np.concatenate(
        [e_agent_keys, rng.choice(wb_agents+nwb_agents, num_inner_agents, replace=False)]
    )

    size[:] = [TOT_AGENTS, num_agents]

    # assign agent properties
    e_agents = dict()
    for agent in e_agent_keys:
        if multi:
            agent_name = f"{seed}_{str(agent)}"
        else:
            agent_name = str(agent)

        agent_attributes = attribute_dict[agent]
        e_agents[agent_name] = Agent(
            agent_name,
            schedule_dict[agent],
            agent_attributes["wallbox"] == "True",
            rng.uniform(float(agent_attributes["lowerBound"]), 1),
            float(agent_attributes["lowerBound"]),
            agent_attributes["home"] == "o",
        )

        if multi:
            for stop in e_agents[agent_name].schedule:
                stop["agent"] = f'{seed}_{stop["agent"]}'

    return e_agents


def read_cells(c_file):
    _LOGGER.info("reading cells")
    cells = set()
    file = csv.DictReader(open(c_file, "r"))
    for c in file:
        cells.add((int(c["cx"]), int(c["cy"])))
    return cells


def read_charging_stations(locations_file):
    _LOGGER.info("reading charging stations")
    charging_stations = dict()
    file = csv.DictReader(open(locations_file, "r"))
    for cs in file:
        charging_stations[(int(cs["cx"]), int(cs["cy"]))] = cs
    return charging_stations


def generate_day(agents_attributes_file, agents_schedules_file, seed, quota):
    _LOGGER.info("creating agents")
    return create_agents(agents_attributes_file, agents_schedules_file, seed, quota)
