import cdd
import csv
from gurobipy import *
from itertools import chain, combinations
from multiprocessing import freeze_support, Manager, Process
import logging
from multiprocessing.pool import ThreadPool
import os

from .const import (
    B_BUDGET,
    B_LIMIT,
    B_PROPORTION,
    BUDGET,
    CAPACITY_CUTS,
    COST_FAST, 
    COST_SLOW,
    CONF_FAST,
    CONF_SLOW,
    FRACTIONAL_ASSIGNMENT,
    LIMIT,
    LOG_FILE,
    METHOD,
    MIN_X,
    MIN_Y,
    MIPGAP,
    OUTER_DESCRIPTION,
    POLYTOPE_THREADS,
    PRESOLVE,
    PROPORTION,
    TIMELIMIT
)
from .fileUtils import silentremove
from .timeUtils import intervalContainsPoint
from .ineqUtils import roundInequality

_LOGGER = logging.getLogger(__name__)
LOG_LEVEL = logging.DEBUG
_LOGGER.setLevel(LOG_LEVEL)

def multi_addRequirementConstraintsOuterWrapper(args):
    return multi_addRequirementConstraintsOuter(*args)

def multi_addRequirementConstraintsOuter(cs_model, agent_key, t_timeout):
    #create vertices
    agent = cs_model._ear[agent_key]
    if not agent.valid_patterns:
        cs_model.addLConstr(cs_model._y.sum(agent_key,"*","*","*","*")>=4*cs_model._z[agent_key],name=f"outer_{agent_key}_{0}")
        cs_model.addLConstr(cs_model._y.sum(agent_key,"*","*","*","f")>=2*cs_model._z[agent_key],name=f"outer_{agent_key}_{1}")
        return True

    feas_vertices=[]
    for vp in agent.valid_patterns:
        indices = [i for i, x in enumerate(vp) if x == 1]
        ind_powerset = chain.from_iterable(combinations(indices, r) for r in range(len(indices)+1))
        variants = []
        for combination in ind_powerset:
            vp_new = list(vp[:])
            for index in combination:
                vp_new[index] = 2
            variants.append(vp_new)
        for v in variants:
            feas_vertices.append([1 if (i==1 and j==0) or (i==2 and j==1) else 0 for i in v for j in range(2)])

    #start constraint calculation
    manager = Manager()
    return_dict = manager.dict()
    p = Process(target=multi_calculateInequalities,args=(feas_vertices,return_dict))
    p.start()
    p.join(t_timeout)
    if p.is_alive():
        p.terminate()
        p.join()

        #create inner constraints instead
        cs_model._w[agent_key] = cs_model.addVars(agent.valid_patterns, vtype=cs_model._fractionalString)
        cs_model.update()
        cs_model.addRequirementConstraintInner(agent)
        return False

    eq_indices = return_dict["eq"]
    ineqs = return_dict["ineqs"]

    for index,ineq in enumerate(ineqs):
        weights = {(index2,speed):ineq[2*index2+1] if speed=="s" else ineq[2*index2+2] for index2 in range(len(cs_model._ear[agent_key].charging_opps)) for speed in cs_model._csSpeeds}
        coeffs = {(agent_key,opp["index"],location[0],location[1],speed):weights[(opp["index"],speed)] for opp in cs_model._ear[agent_key].charging_opps for location in cs_model._rcpb[opp["loc"]] for speed in cs_model._csSpeeds}
        if index in eq_indices:
            cs_model.addLConstr(cs_model._y.prod(coeffs)==-ineq[0]*cs_model._z[agent_key],name=f"outer_{agent_key}_{index}")
        else:
            cs_model.addLConstr(cs_model._y.prod(coeffs)>=-ineq[0]*cs_model._z[agent_key],name=f"outer_{agent_key}_{index}")

    return True

def multi_calculateInequalities(feas_vertices,return_dict):
    mat = cdd.Matrix([[1]+fv for fv in feas_vertices])
    pol = cdd.Polyhedron(mat)

    res = pol.get_inequalities()

    ineqs = [roundInequality(res[i],20,0.0001) for i in range(res.row_size)]

    return_dict["eq"] = list(res.lin_set)
    return_dict["ineqs"] = ineqs
    
    
class csBaseModel(Model):
    def __init__(self,ear,rc,rcpb,rb,**kwargs):
        #create base model
        Model.__init__(self)

        #set values
        prop_defaults = {
            "b_outer": OUTER_DESCRIPTION, 
            "b_cap": CAPACITY_CUTS,
            "i_capMaxCard": 1,
            "b_budget": B_BUDGET,
            "i_budget": BUDGET,
            "b_limit": B_LIMIT,
            "t_limit": LIMIT,
            "b_proportion": B_PROPORTION,
            "f_proportion": PROPORTION,
            "b_fractionalAssignment": FRACTIONAL_ASSIGNMENT,
            "i_method":METHOD, 
            "f_mipgap": MIPGAP,
            "i_timelimit": TIMELIMIT,
            "b_presolve": PRESOLVE,
            "i_polytopeThreads":POLYTOPE_THREADS,
            "s_logFile": LOG_FILE
        }
        for prop, default in prop_defaults.items():
            setattr(self, "_"+prop, kwargs.get(prop, default))

        #set gurobi model parameters
        self.setParam("Method",self._i_method)
        if not self._b_presolve:
            self.setParam("Presolve",0)
        if self._s_logFile:
            silentremove(self._s_logFile)
            self.setParam("LogFile",self._s_logFile)
        if self._f_mipgap:
            self.setParam("MIPGap",self._f_mipgap)
        if self._i_timelimit:
            self.setParam("TimeLimit",self._i_timelimit)

        #constants
        self._csSpeeds = ["f","s"]
        self._csConfigs = {"f":CONF_FAST, "s":CONF_SLOW}
        self._csCosts = {"f":COST_FAST, "s":COST_SLOW}
        self._costFast = COST_FAST
        self._costSlow = COST_SLOW
        self._minX = MIN_X
        self._minY = MIN_Y
        self._numAgents = len(ear)
        self._fractionalString = "C" if self._b_fractionalAssignment else "B"

        #model input
        self._agents = ear.keys()
        self._ear = ear
        self._rc = rc
        self._rcpb = rcpb
        self._rb = rb
        
        #create variables
        self._w = dict()
        if not self._b_outer:
            for key,agent in self._ear.items():
                self._w[key] = self.addVars(agent.valid_patterns, vtype=self._fractionalString)
        self._possibleChargingStations = {(cell[0],cell[1],config,speed):config*self._csCosts[speed] for cell in self._rc for speed in self._csSpeeds for config in self._csConfigs[speed]}
        self._speedConfigs = {cs:cs[2] for cs in self._possibleChargingStations}
        self._x = self.addVars(self._possibleChargingStations, vtype="B")
        self._possibleChargingProcesses = [(key,opp["index"])+location+(speed,) for key,agent in self._ear.items() for opp in agent.charging_opps for location in self._rcpb[opp["loc"]] for speed in self._csSpeeds]
        self._y = self.addVars(self._possibleChargingProcesses, vtype=self._fractionalString)
        if not (self._b_limit or self._b_budget or self._b_proportion):
            self._z = {key:1 for key in self._ear}
        else:
            self._z = self.addVars(self._ear, vtype="B")
        self.update()
        _LOGGER.info("variables added")

    def addStandardConstraints(self):
        self.addRequirementConstraints()
        _LOGGER.info("requirement constraints added")
        self.addMaxCSConstraints()
        _LOGGER.info("max cs constraints added")
        self.addCPPerStopConstraints()
        _LOGGER.info("cp per stop constraints added")
        if not self._b_cap:
            self.addCapacityConstraints()
            _LOGGER.info("capacity constraints added")
        else:
            self.addStrengthenedCapacityDescription()
            _LOGGER.info("strengthened capacity description added")
        if self._b_budget:
            self.addBudgetConstraint()
        elif self._b_limit:
            self.addLimitConstraint()
        if self._b_proportion:
            self.addProportionConstraint()
        self.update()

    def addCSObjective(self):
        if not (self._b_limit or self._b_budget):
            self.setObjective(self._x.prod(self._possibleChargingStations,"*","*","*"),GRB.MINIMIZE)
        else:
            self.setObjective(self._z.sum(),GRB.MAXIMIZE)

    def addRequirementConstraints(self):
        if self._b_outer:
            self.addRequirementConstraintsOuter()
        else:
            self.addRequirementConstraintsInner()

    def addRequirementConstraintsOuter(self,timeout=5):
        if os.name == 'nt':
            freeze_support()
        pool = ThreadPool(self._i_polytopeThreads)
        l = [(self,key,timeout) for key in self._ear]
        suc = pool.map(multi_addRequirementConstraintsOuterWrapper,l)
        return

    def addRequirementConstraintsInner(self):
        for agent in self._ear.values():
            self.addRequirementConstraintInner(agent)
        return

    def addRequirementConstraintInner(self,agent):
        if not agent.valid_patterns:
            self.addLConstr(self._y.sum(agent.name,"*","*","*","*")>=4*self._z[agent.name],name=f"inner_{agent.name}_{0}")
            self.addLConstr(self._y.sum(agent.name,"*","*","*","f")>=2*self._z[agent.name],name=f"inner_{agent.name}_{1}")
            return True

        self.addLConstr(self._w[agent.name].sum()==self._z[agent.name],name=f"innerSat_{agent.name}")
        for index,_ in enumerate(agent.charging_opps):
            for mode in [1,2]:
                if mode==1:
                    coeffs = {vp:1 for vp in agent.valid_patterns if vp[index]}
                    self.addLConstr(self._y.sum(agent.name,index,"*","*","*")>=self._w[agent.name].prod(coeffs),name=f"inner_{agent.name}_{mode}_{index}")
                if mode==2:
                    coeffs = {vp:1 for vp in agent.valid_patterns if vp[index]==2}
                    self.addLConstr(self._y.sum(agent.name,index,"*","*","f")>=self._w[agent.name].prod(coeffs),name=f"inner_{agent.name}_{mode}_{index}")
        return

    def addMaxCSConstraints(self):
        for cell in self._rc:
            self.addLConstr(self._x.sum(cell[0],cell[1],"*","*")<=1,name=f"csMax_{cell}_0")
        return

    def addCPPerStopConstraints(self):
        for key,agent in self._ear.items():
            for opp in agent.charging_opps:
                if (opp["loc"]) in self._rb:
                    self.addLConstr(self._y.sum(key,opp["index"],"*","*","*")<=1,name=f"cpPerStop_{key}_{opp['index']}")
        return

    def addCapacityConstraints(self):
        for cell in self._rc:
            arrivalAtRefPoint = [opp for key,agent in self._ear.items() for opp in agent.charging_opps if cell in self._rcpb[opp["loc"]]]
            for time in [opp["time"][0] for opp in arrivalAtRefPoint]:
                relevantChargingProcesses = [[opp["agent"],opp["index"],cell] for opp in arrivalAtRefPoint if intervalContainsPoint(opp["time"],time)]
                for speed in ["f","s"]:
                    self.addLConstr(quicksum(self._y[index[0],index[1],index[2][0],index[2][1],speed] for index in relevantChargingProcesses) <= self._x.prod(self._speedConfigs,cell[0],cell[1],"*",speed),name=f"capacity_{cell}_{time}_{speed}")
        return

    def addStrengthenedCapacityDescription(self):
        for cell in self._rc:
            subsets = []
            arrivalAtRefPoint = [opp for key,agent in self._ear.items() for opp in agent.charging_opps if cell in self._rcpb[opp["loc"]]]
            for time in [opp["time"][0] for opp in arrivalAtRefPoint]:
                relevantChargingProcesses = [(opp["agent"],opp["index"],cell) for opp in arrivalAtRefPoint if intervalContainsPoint(opp["time"],time)]
                for i in range(1,min(self._i_capMaxCard+1,len(relevantChargingProcesses))):
                    for S in combinations(relevantChargingProcesses,i):
                        if not set(S) in subsets:
                            subsets.append(set(S))
                if not set(relevantChargingProcesses) in subsets:
                    subsets.append(set(relevantChargingProcesses))
            for S in subsets:
                coeffs = {k:min(v,len(S)) for k,v in self._speedConfigs.items()}
                for speed in ["f","s"]:
                    self.addLConstr(quicksum(self._y[index[0],index[1],index[2][0],index[2][1],speed] for index in S) <= self._x.prod(coeffs,cell[0],cell[1],"*",speed),name=f"capacity_{cell}_{time}_{speed}")

        return

    def addLimitConstraint(self):
        self.addLConstr(self._x.prod(self._speedConfigs,"*","*","*","s")<=self._t_limit[0])
        self.addLConstr(self._x.prod(self._speedConfigs,"*","*","*","f")<=self._t_limit[1])

    def addBudgetConstraint(self):
        self.addLConstr(self._x.prod(self._possibleChargingStations,"*","*","*","*")<=self._i_budget)

    def addProportionConstraint(self):
        self.addLConstr(self._z.sum()>=self._f_proportion*self._numAgents)

    def logSolutionStatistics(self):
        self._fastChargingPorts = {cell:sum([self._x[cell[0],cell[1],config,"f"].x*config for config in self._csConfigs["f"]]) for cell in self._rc}
        self._slowChargingPorts = {cell:sum([self._x[cell[0],cell[1],config,"s"].x*config for config in self._csConfigs["s"]]) for cell in self._rc}

        fastChargingProcesses = {cp:self._y[cp].x for cp in self._possibleChargingProcesses if cp[4]=="f"}
        slowChargingProcesses = {cp:self._y[cp].x for cp in self._possibleChargingProcesses if cp[4]=="s"}

        _LOGGER.info(f"no of fast charging ports: {sum([val for key,val in self._fastChargingPorts.items()])}")
        _LOGGER.info(f"no of slow charging ports: {sum([val for key,val in self._slowChargingPorts.items()])}")

        _LOGGER.info(f"no of fast charging processes: {sum([val for key,val in fastChargingProcesses.items()])}")
        _LOGGER.info(f"no of slow charging processes: {sum([val for key,val in slowChargingProcesses.items()])}")

        _LOGGER.info(f"no of agents: {len(self._ear)}")
        _LOGGER.info(f"no of candidate charging stations: {len(self._rc)}")
        return

    def saveSolutionToFile(self,filename):
        file = open(filename,"w")
        dw = csv.DictWriter(file, ["cx", "cy", "fast", "slow", "wkt"])
        dw.writeheader()
        for loc,amount in self._fastChargingPorts.items():
            if amount > 0:
                dw.writerow({
                    "cx":loc[0],
                    "cy":loc[1],
                    "fast":int(amount),
                    "slow":0,
                    "wkt":f"POINT ({self._minX + (loc[0]+0.5)*100} {self._minY + (loc[1]+0.5)*100})"
                    })
        for loc,amount in self._slowChargingPorts.items():
            if amount > 0:
                dw.writerow({
                    "cx":loc[0],
                    "cy":loc[1],
                    "fast":0,
                    "slow":int(amount),
                    "wkt":f"POINT ({self._minX + (loc[0]+0.5)*100} {self._minY + (loc[1]+0.5)*100})"
                    })

        file.close()

    
class csMultiModel(csBaseModel):
    def __init__(self,ear,rc,rcpb,rb,seeds,akps,**kwargs):
        self._seeds = seeds
        self._akps = akps
        csBaseModel.__init__(self,ear,rc,rcpb,rb,**kwargs)
        if self._b_limit or self._b_budget:
            self._s = self.addVar(vtype="I")

    def addCapacityConstraints(self):
        for seed in self._seeds:
            for cell in self._rc:
                arrivalAtRefPoint = [opp for key in self._akps[seed] for opp in self._ear[key].charging_opps if cell in self._rcpb[opp["loc"]]]
                for time in [opp["time"][0] for opp in arrivalAtRefPoint]:
                    relevantChargingProcesses = [[opp["agent"],opp["index"],cell] for opp in arrivalAtRefPoint if intervalContainsPoint(opp["time"],time)]
                    for speed in ["f","s"]:
                        self.addLConstr(quicksum(self._y[index[0],index[1],index[2][0],index[2][1],speed] for index in relevantChargingProcesses) <= self._x.prod(self._speedConfigs,cell[0],cell[1],"*",speed),name=f"capacity_{seed}_{cell}_{time}_{speed}")

    def addStandardConstraints(self):
        super().addStandardConstraints()
        if self._b_limit or self._b_budget:
            self.addSatisfactionConstraints()
            _LOGGER.info("Satisfaction constraints added")

    def addSatisfactionConstraints(self):
        for seed in self._seeds:
            self.addLConstr(self._s<=quicksum(self._z[key] for key in self._akps[seed]),name=f"satisfaction_{seed}")

    def addCSObjective(self):
        if not (self._b_limit or self._b_budget):
            self.setObjective(self._x.prod(self._possibleChargingStations,"*","*","*"),GRB.MINIMIZE)
        else:
            self.setObjective(self._s,GRB.MAXIMIZE)

    def addStrengthenedCapacityDescription(self):
        for seed in self._seeds:
            for cell in self._rc:
                subsets = []
                arrivalAtRefPoint = [opp for key in self._akps[seed] for opp in self._ear[key].charging_opps if cell in self._rcpb[opp["loc"]]]
                for time in [opp["time"][0] for opp in arrivalAtRefPoint]:
                    relevantChargingProcesses = [(opp["agent"],opp["index"],cell) for opp in arrivalAtRefPoint if intervalContainsPoint(opp["time"],time)]
                    for i in range(1,min(self._i_capMaxCard+1,len(relevantChargingProcesses))):
                        for S in combinations(relevantChargingProcesses,i):
                            if not set(S) in subsets:
                                subsets.append(set(S))
                    if not set(relevantChargingProcesses) in subsets:
                        subsets.append(set(relevantChargingProcesses))
                for S in subsets:
                    coeffs = {k:min(v,len(S)) for k,v in self._speedConfigs.items()}
                    for speed in ["f","s"]:
                        self.addLConstr(quicksum(self._y[index[0],index[1],index[2][0],index[2][1],speed] for index in S) <= self._x.prod(coeffs,cell[0],cell[1],"*",speed),name=f"capacity_{cell}_{time}_{speed}")

        return