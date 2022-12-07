import logging

from enum import Enum
from scipy.spatial import cKDTree
from sortedcontainers import SortedDict
from tqdm import tqdm

from .agentUtils import soc_after_break
from .utils import cell_to_point, point_to_cell, primary_strategy
from .const import SEC_PER_DAY

_LOGGER = logging.getLogger(__name__)

class SimulationEngine:
    class Status(Enum):
        LOADED = 1
        SIMULATED = 2
        ERROR = 3

    def __init__(self, e_agents_relevant, cs_dict, inner_cells, radius, fail_radius):
        self.ear = e_agents_relevant
        self.cs_dict = cs_dict
        self.radius = radius
        self.fail_radius = fail_radius
        self.comb_radius = radius // 100
        self.num_total_agents = len(e_agents_relevant)
        self.num_successful_agents = 0
        self.inner_cells = inner_cells

        self.failed_agents = set()
        self.totally_failed_agents = set()
        self.cp_list = []
        self.occupation_dict = {}
        self.ending_stops_dict = SortedDict()
        self.nc_dict = {}
        self.rel_breakpoints = dict()

        self.cs_indices_all = [cell for cell in self.cs_dict]
        self.cs_indices_fast = [cell for cell,cs in self.cs_dict.items() if int(cs["fast"])]
        self.cs_kdtree_all = cKDTree([cell_to_point(*cell) for cell in self.cs_indices_all])
        if self.cs_indices_fast:
            self.cs_kdtree_fast = cKDTree([cell_to_point(*cell) for cell in self.cs_indices_fast])
        else: 
            self.cs_kdtree_fast = False

        self.status = self.Status.LOADED

    def _remove_outdated_strategies(self, agent, lp=[]):
        """forget all strategies that cannot be satisfied anymore"""
        if not lp:
            lp = self.live_pattern_dict[agent]
        strats_to_delete = []
        for p in self.known_strategies_dict[agent]:
            if any([i < p[index] for index, i in enumerate(lp)]):
                strats_to_delete.append(p)
        for strat in strats_to_delete:
            del self.known_strategies_dict[agent][
                self.known_strategies_dict[agent].index(strat)
            ]

    def _search_cs_within_radius(self, x, y, fast):
        """
        find all charging stations of predefined speed within given radius
        return list of cells sorted by increasing distance
        """        
        if fast:
            if not self.cs_kdtree_fast:
                return []
            kdTree = self.cs_kdtree_fast
            indexSet = self.cs_indices_fast
        else:
            kdTree = self.cs_kdtree_all
            indexSet = self.cs_indices_all

        distances,indices = kdTree.query((x,y),k=100,distance_upper_bound=self.radius)
        rel_cells = []
        for i in indices:
            if i<len(indexSet):
                rel_cells.append(indexSet[i])
            else:
                break
        return rel_cells

    def _is_cs_within_radius(self, x, y, fast):
        if fast:
            if not self.cs_kdtree_fast:
                return False
            kdTree = self.cs_kdtree_fast
            indexSet = self.cs_indices_fast
        else:
            kdTree = self.cs_kdtree_all
            indexSet = self.cs_indices_all

        distance,index = kdTree.query((x,y),distance_upper_bound=self.radius)
        return index<len(indexSet)

    def _find_closest_available_cs_within_radius(self, x, y, fast):
        """
        find closest charging station of predefined speed within given radius that is not fully occupied
        return (cell,bool:fast) or (False,False) if there exists no such charging station
        """
        css = self._search_cs_within_radius(x, y, fast)
        if len(css) > 0:
            for key in css:
                space_available_fast = (
                    float(self.cs_dict[key]["fast"]) - self.occupation_dict[key][1]
                ) > 0
                space_available_slow = (
                    float(self.cs_dict[key]["slow"]) - self.occupation_dict[key][0]
                ) > 0
                if (space_available_slow and not fast) or space_available_fast:
                    if fast or not space_available_slow:
                        return key, 1
                    else:
                        return key, 0
        return False, 0

    def _find_closest_available_cs(self, x, y, fast):
        """
        find closest charging station of predefined speed that is not fully occupied
        return (cell,bool:fast) or (False,False) if there exists no such charging station
        """
        if fast:
            if not self.cs_kdtree_fast:
                return False, 0
            kdTree = self.cs_kdtree_fast
            indexSet = self.cs_indices_fast
        else:
            kdTree = self.cs_kdtree_all
            indexSet = self.cs_indices_all

        distances,indices = kdTree.query((x,y),k=100,distance_upper_bound=self.fail_radius)
        
        for i in indices:
            if i==len(indexSet):
                return False, 0
            key = indexSet[i]
            space_available_fast = (
                float(self.cs_dict[key]["fast"]) - self.occupation_dict[key][1]
            ) > 0
            space_available_slow = (
                float(self.cs_dict[key]["slow"]) - self.occupation_dict[key][0]
            ) > 0
            if (space_available_slow and not fast) or space_available_fast:
                if fast or not space_available_slow:
                    return key, 1
                else:
                    return key, 0

        return False, 0

    def _compute_patterns(self, zero_break):
        _LOGGER.info("computing patterns")
        if not self.rel_breakpoints:
            for agent in self.ear.values():
                for stop in agent.schedule:
                    bp = (
                        float(stop["sx"]),
                        float(stop["sy"]),
                    )
                    if self._is_cs_within_radius(*bp, True):
                        self.rel_breakpoints[bp] = "f"
                    elif self._is_cs_within_radius(*bp, False):
                        self.rel_breakpoints[bp] = "s"

        for agent in self.ear.values():
            agent.compute_valid_patterns(self.rel_breakpoints, zero_break=zero_break)
            if not agent.valid_patterns:
                gp = agent.calculate_greedy_pattern(
                    self.rel_breakpoints, zero_break=zero_break
                )
                if gp:
                    agent.valid_patterns = [gp]
                else:
                    agent.valid_patterns = [
                        agent.calculate_greedy_pattern(
                            {
                                opp["loc"]: "f"
                                for opp in agent.charging_opps
                                if point_to_cell(*opp["loc"]) in self.inner_cells
                            },
                            zero_break=zero_break,
                        )
                    ]
                    if agent.valid_patterns == [False]:
                        raise AssertionError(
                            f"no valid pattern at all for agent {agent.name}"
                        )
                    self.failed_agents.add(agent.name)

    def _run_simulation(self):
        # collect breaks
        _LOGGER.info("setting up simulation")
        self.time_dict = dict()
        self.end_times = set()
        self.end_times.add(0)
        for key, agent in self.ear.items():
            for index, opp in enumerate(agent.charging_opps):
                t = opp["time"][0]
                self.end_times.add(opp["time"][1])
                if t in self.time_dict:
                    self.time_dict[t].append((key, index))
                else:
                    self.time_dict[t] = [(key, index)]

        # run simulation
        _LOGGER.info("running simulation")
        if not self.occupation_dict:
            self.occupation_dict = {cs: [0, 0] for cs in self.cs_dict}
        self.live_pattern_dict = {key: [] for key in self.ear}
        self.primary_strategy_dict = {
            key: primary_strategy(agent.valid_patterns)
            for key, agent in self.ear.items()
        }
        self.known_strategies_dict = {
            key: agent.valid_patterns[:] for key, agent in self.ear.items()
        }
        for key in self.end_times:
            if not key in self.ending_stops_dict:
                self.ending_stops_dict[key] = []

        self.num_relevant_agents = len([0 for k,_ in self.ear.items() if any(self.primary_strategy_dict[k])])

        finished_agents = set()

        pbar = tqdm(sorted(self.time_dict.items()))
        for t, stops in pbar:
            # release free charging stations
            ending_stops_to_delete = []
            for t_end in self.ending_stops_dict.keys():
                if t>t_end:
                    stops_end = self.ending_stops_dict[t_end]
                    for cs in stops_end:
                        self.occupation_dict[(cs[0], cs[1])][cs[2]] -= 1
                    ending_stops_to_delete.append(t_end)
                else:
                    break

            for estd in ending_stops_to_delete:
                del self.ending_stops_dict[estd]

            # process beginning stops
            for stop in stops:
                agent, index = stop

                # agents that cannot be fixed
                if agent in self.totally_failed_agents or agent in finished_agents:
                    continue

                # check strategies and decide charging behavior
                stop_info = self.ear[agent].charging_opps[index]
                strat = self.primary_strategy_dict[agent]
                if not any(strat[index:]):
                    self.live_pattern_dict[agent] += [0] * (len(strat) - index)
                    finished_agents.add(agent)
                    continue
                search = strat[index]

                seconds = stop_info["time"][0]
                if logging.root.level <= logging.INFO and not seconds % 60:
                    hours = seconds // 3600
                    minutes = (seconds % 3600) // 60
                    pbar.set_description(f"{hours:02d}:{minutes:02d}")

                # primary strategy not indicating charging
                if not search:
                    self.live_pattern_dict[agent].append(0)
                    self._remove_outdated_strategies(agent)
                    continue

                # active agents
                elif agent not in self.failed_agents:
                    # search for nearby (unoccupied) charging stations
                    key, speed = self._find_closest_available_cs_within_radius(
                        *stop_info["loc"], bool(search - 1)
                    )
                    if key:
                        self.occupation_dict[key][speed] += 1
                        self.cp_list.append((agent, index, key, speed))
                        self.ending_stops_dict[stop_info["time"][1]] += [
                            [key[0], key[1], speed]
                        ]
                        self.live_pattern_dict[agent].append(speed + 1)
                        self._remove_outdated_strategies(agent)
                        continue

                    # no fitting cs found. Try alternative strategy
                    if (
                        search == 2
                    ):  # fast charging failed, try slow charging or switch to strategy not charging at the moment
                        self._remove_outdated_strategies(
                            agent, lp=self.live_pattern_dict[agent] + [1]
                        )
                        if self.known_strategies_dict[agent]:
                            self.primary_strategy_dict[agent] = primary_strategy(
                                self.known_strategies_dict[agent]
                            )
                        else:
                            gp = self.ear[agent].calculate_greedy_pattern(
                                self.rel_breakpoints,
                                start_pattern=self.live_pattern_dict[agent] + [1],
                            )
                            if gp:
                                self.known_strategies_dict[agent] = [gp]
                                self.primary_strategy_dict[agent] = gp

                        # try finding slow charging station instead
                        if (
                            self.primary_strategy_dict[agent][index]
                            and self.known_strategies_dict[agent]
                        ):
                            key, speed = self._find_closest_available_cs_within_radius(
                                *stop_info["loc"], False
                            )
                            if key:
                                self.occupation_dict[key][0] += 1
                                self.cp_list.append((agent, index, key, speed))
                                self.ending_stops_dict[stop_info["time"][1]] += [
                                    [key[0], key[1], 0]
                                ]
                                self.live_pattern_dict[agent].append(1)
                                self._remove_outdated_strategies(agent)
                                continue
                        elif not self.primary_strategy_dict[agent][index]:
                            self.live_pattern_dict[agent].append(0)
                            self._remove_outdated_strategies(agent)
                            continue

                    self._remove_outdated_strategies(
                        agent, lp=self.live_pattern_dict[agent] + [0]
                    )
                    if self.known_strategies_dict[
                        agent
                    ]:  # there is a valid known strategy left that does not charge right now
                        self.live_pattern_dict[agent].append(0)
                        self.primary_strategy_dict[agent] = primary_strategy(
                            self.known_strategies_dict[agent]
                        )
                        continue
                    else:
                        gp = self.ear[agent].calculate_greedy_pattern(
                            self.rel_breakpoints,
                            start_pattern=self.live_pattern_dict[agent] + [0],
                        )
                        if (
                            gp
                        ):  # there is a valid (greedy) strategy left that does not charge right now
                            self.live_pattern_dict[agent].append(0)
                            self.primary_strategy_dict[agent] = gp
                            self.known_strategies_dict[agent] = [gp]
                            continue

                    # failed
                    self.failed_agents.add(agent)

                # failed agent
                if not self.primary_strategy_dict[agent][
                    index
                ]:  # do we want to charge at the moment?
                    self.live_pattern_dict[agent].append(0)
                    continue

                # search for closest (unoccupied) charging stations
                key, speed = self._find_closest_available_cs(
                    *stop_info["loc"], bool(search - 1)
                )
                if key:
                    self.live_pattern_dict[agent].append(speed + 1)
                    self.occupation_dict[key][speed] += 1
                    self.cp_list.append((agent, index, key, speed))
                    self.ending_stops_dict[stop_info["time"][1]] += [
                        [key[0], key[1], speed]
                    ]
                else:
                    self.totally_failed_agents.add(agent)
        return

    def simulate(self, warm_start=0):
        if not self.status == self.Status.LOADED:
            raise AssertionError("Please create a new simulation engine")

        for i in range(warm_start + 1):
            self._compute_patterns(zero_break=(i == 0))
            self.nc_dict = {a: (k, s) for a, index, k, s in self.cp_list}
            self.nc_before_dict = {
                k: self.soc_before_dict[k, len(self.ear[k].charging_opps) - 1]
                for k, v in self.nc_dict.items()
            }
            self.failed_agents = set()
            self.totally_failed_agents = set()
            self._run_simulation()
            if i < warm_start:
                self.cp_list = [
                    (a, 0, k, s)
                    for a, index, k, s in self.cp_list
                    if len(self.ear[a].schedule) == index
                ]
                agents = [self.ear[cp[0]] for cp in self.cp_list]
                ca = zip(self.cp_list, agents)
                opps = [a.charging_opps[c[1]] for c,a in ca]
                times = [opp["time"][1] for opp in opps]
                self.ending_stops_dict = SortedDict()
                self.occupation_dict = {cs: [0, 0] for cs in self.cs_dict}
                for t in times:
                    self.ending_stops_dict[t % SEC_PER_DAY] = []
                cat = zip(self.cp_list, agents, times)
                for c,a,t in cat:
                    self.ending_stops_dict[t % SEC_PER_DAY] += [(c[2][0],c[2][1],c[3])]
                    self.occupation_dict[c[2]][c[3]]+=1

                self._calculate_frame_soc()
                for agent, soc in self.soc_after_dict.items():
                    if not self.ear[agent].homecharger:
                        self.ear[agent].soc_start = soc

        self.num_successful_agents = self.num_relevant_agents - len(self.failed_agents)
        self.status = self.Status.SIMULATED

    def _calculate_frame_soc(self):
        _LOGGER.info("calculating frame soc")
        self.soc_before_dict = dict()
        self.soc_after_dict = dict()
        for key, agent in self.ear.items():
            if not key in self.totally_failed_agents:
                # only relevant if no warmstart
                if self.live_pattern_dict[key][0]:
                    if int(agent.schedule[-1]["t_start"]) < SEC_PER_DAY:
                        self.soc_before_dict[(key, 0)] = soc_after_break(
                            agent.soc_start,
                            self.live_pattern_dict[key][0] - 1,
                            SEC_PER_DAY - int(agent.schedule[-1]["t_start"]),
                        )
                    else:
                        self.soc_before_dict[(key, 0)] = agent.soc_start
                    soc = soc_after_break(
                        agent.soc_start,
                        self.live_pattern_dict[key][0] - 1,
                        (
                            int(agent.schedule[-1]["t_end"])
                            - int(agent.schedule[-1]["t_start"])
                        )
                        % SEC_PER_DAY,
                    )
                # check if there was nightcharging in warmstart
                elif key in self.nc_dict:
                    if int(agent.schedule[-1]["t_start"]) < SEC_PER_DAY:
                        self.soc_before_dict[(key, 0)] = soc_after_break(
                            self.nc_before_dict[key],
                            self.nc_dict[key][1],
                            SEC_PER_DAY - int(agent.schedule[-1]["t_start"]),
                        )
                    else:
                        self.soc_before_dict[(key, 0)] = self.nc_before_dict[key]
                    soc = agent.soc_start
                else:
                    soc = agent.soc_start
                for index, stop in enumerate(agent.schedule):
                    soc -= float(stop["distance"]) / (agent.range * 1000)
                    if self.live_pattern_dict[key][index + 1]:
                        self.soc_before_dict[(key, index + 1)] = soc
                        soc = soc_after_break(
                            soc,
                            self.live_pattern_dict[key][index + 1] - 1,
                            int(stop["t_end"]) - int(stop["t_start"]),
                        )
                if soc < agent.soc_end:
                    raise AssertionError(
                        f"soc(={soc}) of agent {agent.name} is smaller than his required end soc {agent.soc_end}"
                    )
                self.soc_after_dict[key] = soc


    def get_happy_quota(self,groundset="all"):
        if groundset=="demand":
            return self.num_successful_agents/self.num_relevant_agents
        elif groundset=="all":
            return (self.num_total_agents-len(self.failed_agents))/self.num_total_agents
