def hmsToS(hms):
    return sum(p*q for p,q in zip([int(x) for x in hms.split(":")],(60*60,60,1)))

def intervalContainsPoint(t_interval,t_point):
    return t_interval[0]<=t_point and t_point<=t_interval[1]