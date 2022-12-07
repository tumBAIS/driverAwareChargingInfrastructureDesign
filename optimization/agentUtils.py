#external imports
import csv
import itertools
import math
import numpy as np

from .const import (
    SEC_PER_DAY,
    EFFCSPEED_SLOW,
    MIN_CHARGE_EOD,
    MIN_CHARGE,
    O_QUOTA,
    TOT_AGENTS,
    TOT_CAP,
    TOT_RANGE
)

def soc_after_break(initial, fast, duration, cap, reverse=False):
    """
    calculate soc after a break depending on duration, initial charge and type
    return new soc as percentage
    """
    if cap==50:
        return soc_after_break_50(initial,fast,duration,reverse)#
    else:
        raise AssertionError(f"Capacitiy {cap} unknown!")

def soc_after_break_50(initial,fast,duration,reverse):
    if fast:
        soc = initial * 50
        if soc < 0:
            raise AssertionError(f"soc(={initial}) smaller than 0!")
        if soc <= 15:#50*.3
            t0 = soc*36
        elif soc <= 35:#50*.7
            t0 = 1440 * math.log(-(40 * math.exp(3/8))/(-55 + soc))
        elif soc <= 40:#50*.8
            t0 = 36 * (-55 + 2 *soc + 40 * math.log(2))
        elif soc <= 50:
            t0 = 1200 * math.log(-(100 * 2**(1/5) * math.exp(3/4))/(-170 + 3 * soc))
        else:
            raise AssertionError(f"soc(={initial}) bigger than 1!")

        if not reverse:
            t1 = t0 + duration
        else:
            t1 = max(0, t0 - duration)
        if t1 >= 60 * (15 + 20 * math.log(5) + math.log(16)):
            return 1
        elif t1 >= 900 + 180 * math.log(256):
            return 1/15 * (17 - 10 * 2**(1/5) * math.exp(3/4 - t1/1200))
        elif t1 >= 540 + 180 * math.log(256):
            return t1 / 3600 + 11/20 - 2/5 * math.log(2)
        elif t1 >= 540:
            return 11/10 - 4/5 * math.exp(3/8 - t1/1440)
        elif t1 >= 0:
            return t1 / 1800
        else:
            raise AssertionError(f"t1(={t1}) smaller than 0")

    else:
        if not reverse:
            return min(1, initial + EFFCSPEED_SLOW * duration / 50 * 1 / 3600)
        else:
            return max(0, initial - EFFCSPEED_SLOW * duration / 50 * 1 / 3600)


def c_speed(soc, fast, cap):
    if cap==50:
        return c_speed_50(soc,fast)#
    else:
        raise AssertionError(f"Capacitiy {cap} unknown!")

def c_speed_50(soc, fast):
    """return charging speed depending on given soc (lookup for fast charging speed)"""
    if soc == 1.0:
        return 0
    elif fast:
        if soc < 0.3:
            return 100
        elif soc < 0.7:
            return 137.5-125*soc
        elif soc < 0.8:
            return 50
        else:
            return 170-150*soc
    else:
        return EFFCSPEED_SLOW

def read_schedules(filename):
    scheduleDict = dict()
    file = csv.DictReader(open(filename, "r"))
    for stop in file:
        if stop["agent"] in scheduleDict:
            scheduleDict[stop["agent"]].append(stop)
        else:
            scheduleDict[stop["agent"]]=[stop]

    return scheduleDict

def read_attributes(filename):
    attributeDict = dict()
    file = csv.DictReader(open(filename, "r"))
    o_agents = list()
    wb_agents = list()
    nwb_agents = list()
    for attributes in file:
        attributeDict[attributes["id"]]=attributes
        if attributes["home"]=="o":
            o_agents.append(attributes["id"])
        elif attributes["wallbox"]=="True":
            wb_agents.append(attributes["id"])
        else:
            nwb_agents.append(attributes["id"])

    return attributeDict, o_agents, wb_agents, nwb_agents

#return list of relevant agents
def createMultiEAgents(seeds, e_quota, schedule_file, attribute_file):
    scheduleDict = read_schedules(schedule_file)
    attributeDict, o_agents, wb_agents, nwb_agents = read_attributes(attribute_file)
    e_agents_relevant = {}
    agentKeysPerSeed = {}
    for seed in seeds:
        ear = agentCreator(seed, e_quota, scheduleDict, attributeDict, o_agents, wb_agents, nwb_agents, multi=True)
        agentKeysPerSeed[seed]=list(ear.keys())
        e_agents_relevant.update(ear)

    return e_agents_relevant, agentKeysPerSeed

def createEAgents(seed, e_quota, schedule_file, attribute_file, size=[0,0]):
    scheduleDict = read_schedules(schedule_file)
    attributeDict, o_agents, wb_agents, nwb_agents = read_attributes(attribute_file)
    return agentCreator(seed, e_quota, scheduleDict, attributeDict, o_agents, wb_agents, nwb_agents, size=size)

def agentCreator(seed, e_quota, scheduleDict, attributeDict, o_agents, wb_agents, nwb_agents, multi=False, size=[0,0]):
    #init
    rng = np.random.default_rng(seed)

    num_agents = round(TOT_AGENTS*e_quota)
    num_outerAgents = round(O_QUOTA*num_agents)
    num_innerAgents = num_agents-num_outerAgents

    e_agent_keys = rng.choice(o_agents,num_outerAgents,replace=False)
    e_agent_keys = np.concatenate([e_agent_keys,rng.choice(wb_agents+nwb_agents,num_innerAgents,replace=False)])

    size[:]=[TOT_AGENTS,num_agents]

    #assign agent properties
    e_agents = dict()
    for agent in e_agent_keys:
        if multi:
            agent_name = f"{seed}_{str(agent)}"
        else:
            agent_name = str(agent)

        agentAttributes = attributeDict[agent]
        e_agents[agent_name] = Agent(agent_name,
                                    scheduleDict[agent],
                                    agentAttributes["wallbox"]=="True",
                                    rng.uniform(float(agentAttributes["lowerBound"]),1),
                                    float(agentAttributes["lowerBound"]),
                                    agentAttributes["home"]=="o")
        if multi:
            for stop in e_agents[agent_name].schedule:
                stop["agent"] = f'{seed}_{stop["agent"]}'

    e_agents_relevant = {key:agent for key,agent in e_agents.items() if agent.is_relevant()}
    return e_agents_relevant  

#add stop to corresponding sets if it is valid
def addValidStop(index,bp,breakpoints_filter,valid_stops,valid_fastStops):
    if bp in breakpoints_filter:
        valid_stops.add(index)
        if breakpoints_filter[bp]=="f":
            valid_fastStops.add(index)
    return
        
#agent class
class Agent:
    def __init__(self,name,schedule,homecharger,soc_start,soc_end,outer,tot_range=0,min_charge_eod=MIN_CHARGE_EOD,min_charge=MIN_CHARGE):
        self.name = name
        self.schedule = schedule
        if not tot_range:
            self.range = TOT_RANGE
        else:
            self.range = tot_range
        self.consumption = sum([float(stop["distance"]) for stop in schedule]) / (self.range * 1000)
        self.homecharger = homecharger or outer
        self.soc_start = 1 if self.homecharger else soc_start
        self.soc_end = min_charge_eod if self.homecharger else soc_end
        self.min_charge = min_charge
        self.min_charge_eod = min_charge_eod
        self.num_stops = len(self.schedule)+1
        self.outer=outer
        self.charging_opps = [{"index":0,
                                "agent":name,
                                "time":(0,int(self.schedule[-1]["t_end"])%SEC_PER_DAY),
                                "loc":(float(self.schedule[0]["sx"]),float(self.schedule[0]["sy"]))
                            }] + [{
                                "index":index+1,
                                "agent":name,
                                "time":(int(stop["t_start"]),int(stop["t_end"])),
                                "loc":(float(stop["ex"]),float(stop["ey"]))} 
                            for index,stop in enumerate(self.schedule)]

        #for simulation 
        self.valid_bps = dict()

    #check if agent needs to charge
    #return bool
    def is_relevant(self):
        return self.soc_start-self.soc_end<self.consumption

    #check if given pattern is valid
    #return bool
    def is_validPattern(self,combination):
        if combination[0]:
            soc = 1.0
        else:
            soc = self.soc_start

        for index,stop in enumerate(self.schedule[:-1]):
            soc -= float(stop["distance"])/(self.range*1000)
            if soc < self.min_charge:
                return False
            if combination[index+1]:
                soc = soc_after_break(soc,combination[index+1]-1,int(stop["t_end"])-int(stop["t_start"]),TOT_CAP)
        soc -= float(self.schedule[-1]["distance"])/(self.range*1000)
        if soc < self.min_charge_eod:
            return False
        if not combination[-1]:
            if soc < self.soc_end:
                return False
        return True

    #calculate all valid patterns with a maximum number of max_exactStops charging stops and save in agent
    def calculatePatterns(self,breakpoints_filter,max_exactStops=3):
        self.valid_patterns = []
        valid_stops = set()
        valid_fastStops = set()
        for index,stop in enumerate(self.schedule):
            bp = (float(stop["sx"]),float(stop["sy"]))
            addValidStop(index,bp,breakpoints_filter,valid_stops,valid_fastStops)
        stop = self.schedule[-1]
        bp = (float(stop["ex"]),float(stop["ey"]))
        addValidStop(len(self.schedule),bp,breakpoints_filter,valid_stops,valid_fastStops)

        stop_combinations = [tuple([2 if k in fast_assignment else 1 if k in stop_set else 0 for k in range(self.num_stops)])
                             for i in range(1,max_exactStops+1) 
                             for stop_set in itertools.combinations(valid_stops,i) 
                             for j in range(len(valid_fastStops.intersection(set(stop_set)))+1) 
                             for fast_assignment in itertools.combinations(valid_fastStops.intersection(set(stop_set)),j)]

        while stop_combinations:
            combination = stop_combinations.pop(0)
            if not self.is_validPattern(combination):
                continue
            self.valid_patterns += [combination]
            dominated = []
            for c in stop_combinations:
                if all([x[0]<=x[1] for x in zip(combination,c)]):
                    dominated.append(c)

            for c in dominated:
                stop_combinations.pop(stop_combinations.index(c))

        return

    #calculate greedy pattern with respect to some starting pattern
    #return greedy pattern or False if there is none
    def calculateGreedyPattern(self,breakpoints_filter,start_pattern=[]):
        valid_stops = set()
        valid_fastStops = set()
        for index,stop in enumerate(self.schedule):
            bp = (float(stop["sx"]),float(stop["sy"]))
            addValidStop(index,bp,breakpoints_filter,valid_stops,valid_fastStops)
        stop = self.schedule[-1]
        bp = (float(stop["ex"]),float(stop["ey"]))
        addValidStop(len(self.schedule),bp,breakpoints_filter,valid_stops,valid_fastStops)
        if not self.is_validPattern(start_pattern+[2 if i in valid_fastStops else 1 if i in valid_stops else 0 for i in range(len(start_pattern),self.num_stops)]):
            return False
        
        greedy_pattern = start_pattern+[2 if i in valid_fastStops else 1 if i in valid_stops else 0 for i in range(len(start_pattern),self.num_stops)]
        for i in range(self.num_stops-1,len(start_pattern)-1,-1):
            if self.is_validPattern([0 if index==i else g for index,g in enumerate(greedy_pattern)]):
                greedy_pattern[i]=0
            elif i in valid_stops and self.is_validPattern([1 if index==i else g for index,g in enumerate(greedy_pattern)]):
                greedy_pattern[i]=1
        return greedy_pattern