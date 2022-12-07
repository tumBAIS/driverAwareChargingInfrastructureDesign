from functools import reduce
from math import gcd

#round inequality to integers
def roundInequality(ineq,maxM,accM):
    #find smallest multiplier <maxM for every entry st it becomes integer
    multipliers = [1]*len(ineq)
    for index,i in enumerate(ineq):
        multipliers[index] = findMultiplier(i,maxM,accM)
    #find smallest common multiple of the multipliers
    leastCommonMultiplier = reduce(lcm,multipliers)
    ineq = [round(leastCommonMultiplier*i) for i in ineq]
    return ineq

#find the least common multiple of two integers 
def lcm(a,b):
    return a*b//gcd(a,b)

#find the smallest multiplier of a fractional value, s.t. it becomes integral
def findMultiplier(frac,maxM,accM):
    for m in range(1,maxM):
        if abs(m*frac-round(m*frac))<accM:
            return m
    raise ValueError(f"No valid multiplier for value {frac} found. Consider increasing the maximum multiplier or the accuracy value.")