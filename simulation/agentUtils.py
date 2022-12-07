import math

from .const import EFFCSPEED_SLOW, TOT_CAP


def soc_after_break(initial, fast, duration, cap=TOT_CAP, reverse=False):
    """
    calculate soc after a break depending on duration, initial charge and type
    return new soc as percentage
    """
    if cap==77:
        return soc_after_break_77(initial,fast,duration,reverse)#
    elif cap==50:
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


def soc_after_break_77(initial,fast,duration,reverse):
    if fast:
        soc = initial * 77
        if soc < 0:
            raise AssertionError(f"soc(={initial}) smaller than 0!")
        if soc <= 30.8:#77*.4
            t0 = soc * 32
        elif soc <= 61.6:#77*.8
            t0 = 9856 / 5 * (1 / 2 - math.log(3 / 2 - 5 / 308 * soc))
        elif soc <= 69.3:#77*.9
            t0 = (soc - 61.6) * 64 + 4928 / 5 * (1 + 2 * math.log(2))
        elif soc <= 77:
            t0 = 1232 * (6 / 5 - math.log(2 ** (2 / 5) / 77 * (1771 / 20 - soc)))
        else:
            raise AssertionError(f"soc(={initial}) bigger than 1!")

        if not reverse:
            t1 = t0 + duration
        else:
            t1 = max(0, t0 - duration)
        if t1 >= 1232 / 5 * (6 + math.log(800000 / 243)):
            return 1
        elif t1 >= 4928 / 5 * (3 / 2 + 2 * math.log(2)):
            return 23 / 20 - 2 ** (-2 / 5) * math.exp(6 / 5 - t1 / 1232)
        elif t1 >= 4928 / 5 * (1 + 2 * math.log(2)):
            return t1 / 4928 - 1 / 5 * (1 + 2 * math.log(2)) + 4 / 5
        elif t1 >= 4928 / 5:
            return 2 / 5 * (3 - 2 * math.exp(1 / 2 - 5 * t1 / 9856))
        elif t1 >= 0:
            return t1 / 2464
        else:
            raise AssertionError(f"t1(={t1}) smaller than 0")

    else:
        if not reverse:
            return min(1, initial + EFFCSPEED_SLOW * duration / 77 * 1 / 3600)
        else:
            return max(0, initial - EFFCSPEED_SLOW * duration / 77 * 1 / 3600)


def time_to_full_charge(initial, fast, cap=TOT_CAP):
    if cap==77:
        return time_to_full_charge_77(initial,fast)#
    elif cap==50:
        return time_to_full_charge_50(initial,fast)#
    else:
        raise AssertionError(f"Capacitiy {cap} unknown!")

        
def time_to_full_charge_50(initial,fast):
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

        return 1200 * math.log(-(100 * 2**(1/5) * math.exp(3/4))/(-20)) - t0

    else:
        return (1 - initial) * 3600 * 50 / EFFCSPEED_SLOW

def time_to_full_charge_77(initial,fast):
    if fast:
        soc = initial * 77
        if soc < 0:
            raise AssertionError(f"soc(={initial}) smaller than 0!")
        if soc <= 30.8:
            t0 = soc * 32
        elif soc <= 61.6:
            t0 = 9856 / 5 * (1 / 2 - math.log(3 / 2 - 5 / 308 * soc))
        elif soc <= 69.3:
            t0 = (soc - 61.6) * 64 + 4928 / 5 * (1 + 2 * math.log(2))
        elif soc <= 77:
            t0 = 1232 * (6 / 5 - math.log(2 ** (2 / 5) / 77 * (1771 / 20 - soc)))
        else:
            raise AssertionError(f"soc(={initial}) bigger than 1!")

        return 1232 / 5 * (6 + math.log(800000 / 243)) - t0

    else:
        return (1 - initial) * 3600 * 77 / EFFCSPEED_SLOW


def add_valid_stop(index, bp, breakpoints_filter, valid_stops, valid_fast_stops):
    """add stop to corresponding sets if it is valid"""
    if bp in breakpoints_filter:
        valid_stops.add(index)
        if breakpoints_filter[bp] == "f":
            valid_fast_stops.add(index)


def c_speed(soc, fast, cap=TOT_CAP):
    if cap==77:
        return c_speed_77(soc,fast)#
    elif cap==50:
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


def c_speed_77(soc, fast):
    """return charging speed depending on given soc (lookup for fast charging speed)"""
    if soc == 1.0:
        return 0
    elif fast:
        if soc < 0.4:
            return 112.5
        elif soc < 0.8:
            return 168.75 - soc * 140.625
        elif soc < 0.9:
            return 56.25
        else:
            return 258.75 - soc * 225
    else:
        return EFFCSPEED_SLOW

def soc_after_break_list(initial, fast, durations, cap=TOT_CAP):
    """
    calculate soc after a break depending on duration, initial charge and type
    return new soc as percentage
    """
    if cap==77:
        return soc_after_break_list_77(initial,fast,durations)#
    elif cap==50:
        return soc_after_break_list_50(initial,fast,durations)#
    else:
        raise AssertionError(f"Capacitiy {cap} unknown!")

def soc_after_break_list_77(initial, fast, durations):
    if fast:
        soc = initial * 77
        if soc < 0:
            raise AssertionError(f"soc(={initial}) smaller than 0!")
        if soc <= 30.8:
            t0 = soc * 32
        elif soc <= 61.6:
            t0 = 9856 / 5 * (1 / 2 - math.log(3 / 2 - 5 / 308 * soc))
        elif soc <= 69.3:
            t0 = (soc - 61.6) * 64 + 4928 / 5 * (1 + 2 * math.log(2))
        elif soc <= 77:
            t0 = 1232 * (6 / 5 - math.log(2 ** (2 / 5) / 77 * (1771 / 20 - soc)))
        else:
            raise AssertionError(f"soc(={initial}) bigger than 1!")

        socs = []
        t1s = [t0+duration for duration in durations]
        for t1 in t1s:
            if t1 >= 1232 / 5 * (6 + math.log(800000 / 243)):
                socs.append(1)
            elif t1 >= 4928 / 5 * (3 / 2 + 2 * math.log(2)):
                socs.append(23 / 20 - 2 ** (-2 / 5) * math.exp(6 / 5 - t1 / 1232))
            elif t1 >= 4928 / 5 * (1 + 2 * math.log(2)):
                socs.append(t1 / 4928 - 1 / 5 * (1 + 2 * math.log(2)) + 4 / 5)
            elif t1 >= 4928 / 5:
                socs.append(2 / 5 * (3 - 2 * math.exp(1 / 2 - 5 * t1 / 9856)))
            elif t1 >= 0:
                socs.append(t1 / 2464)
            else:
                raise AssertionError(f"t1(={t1}) smaller than 0")
        return socs

    else:
        return [min(1, initial + EFFCSPEED_SLOW * duration / 77 * 1 / 3600) for duration in durations]


def soc_after_break_list_50(initial, fast, durations):
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

        socs = []
        t1s = [t0+duration for duration in durations]
        for t1 in t1s:
            if t1 >= 60 * (15 + 20 * math.log(5) + math.log(16)):
                socs.append(1)
            elif t1 >= 900 + 180 * math.log(256):
                socs.append(1/15 * (17 - 10 * 2**(1/5) * math.exp(3/4 - t1/1200)))
            elif t1 >= 540 + 180 * math.log(256):
                socs.append(t1 / 3600 + 11/20 - 2/5 * math.log(2))
            elif t1 >= 540:
                socs.append(11/10 - 4/5 * math.exp(3/8 - t1/1440))
            elif t1 >= 0:
                socs.append(t1 / 1800)
            else:
                raise AssertionError(f"t1(={t1}) smaller than 0")
        return socs

    else:
        return [min(1, initial + EFFCSPEED_SLOW * duration / 50 * 1 / 3600) for duration in durations]
