import itertools

from .const import MAX_EXACT_STOPS, SEC_PER_DAY, TOT_RANGE, MIN_CHARGE, MIN_CHARGE_EOD
from .agentUtils import add_valid_stop, soc_after_break


class Agent:
    def __init__(
        self,
        name,
        schedule,
        homecharger,
        soc_start,
        soc_end,
        outer,
        tot_range=TOT_RANGE,
        min_charge_eod=MIN_CHARGE_EOD,
        min_charge=MIN_CHARGE,
    ):
        self.name = name
        self.schedule = schedule
        if int(self.schedule[0]["t_start"])>=SEC_PER_DAY:
            for x in self.schedule:
                x["t_start"] = int(x["t_start"])-SEC_PER_DAY
                x["t_end"] = int(x["t_end"])-SEC_PER_DAY
        self.consumption = sum([float(stop["distance"]) for stop in schedule]) / (
            tot_range * 1000
        )
        self.homecharger = homecharger or outer
        self.range = tot_range
        self.soc_start = 1 if self.homecharger else soc_start
        self.soc_end = min_charge_eod if self.homecharger else soc_end
        self.min_charge = min_charge
        self.min_charge_eod = min_charge_eod
        self.num_stops = len(self.schedule) + 1
        self.outer = outer
        self.charging_opps = [#based on the assumption of reasonable times
            {
                "index": 0,
                "agent": name,
                "time": (max(-1,int(self.schedule[-1]["t_start"]) - SEC_PER_DAY), int(self.schedule[-1]["t_end"]) % SEC_PER_DAY),
                "loc": (float(self.schedule[0]["sx"]), float(self.schedule[0]["sy"])),
                "act": "home",
            }
        ] + [
            {
                "index": index + 1,
                "agent": name,
                "time": (int(stop["t_start"]), int(stop["t_end"])),
                "loc": (float(stop["ex"]), float(stop["ey"])),
                "act": stop["act"],
            }
            for index, stop in enumerate(self.schedule)
        ]

        # for simulation
        self.valid_bps = dict()

    # check if agent needs to charge
    # return bool
    def is_relevant(self):
        return self.soc_start - self.consumption < self.soc_end

    # check if given pattern is valid
    # return bool
    def is_valid_pattern(self, combination):
        if combination[0]:
            soc = soc_after_break(
                self.soc_start,
                combination[0] - 1,
                (int(self.schedule[-1]["t_end"]) - int(self.schedule[-1]["t_start"]))
                % SEC_PER_DAY,
            )
        else:
            soc = self.soc_start

        for index, stop in enumerate(self.schedule[:-1]):
            soc -= float(stop["distance"]) / (self.range * 1000)
            if soc < self.min_charge:
                return False
            if combination[index + 1]:
                soc = soc_after_break(
                    soc,
                    combination[index + 1] - 1,
                    int(stop["t_end"]) - int(stop["t_start"]),
                )
        soc -= float(self.schedule[-1]["distance"]) / (self.range * 1000)
        if soc < self.min_charge_eod:
            return False
        if soc >= self.soc_end:
            return True
        elif not combination[-1]:
            return False
        else:
            soc = soc_after_break(
                soc,
                combination[-1] - 1,
                (int(self.schedule[-1]["t_end"]) - int(self.schedule[-1]["t_start"]))
                % SEC_PER_DAY,
            )
            if soc >= self.soc_end:
                return True
            else:
                return False

    def compute_valid_patterns(self, breakpoints_filter, zero_break=True):
        """
        calculate all valid patterns with a maximum number of MAX_EXACT_STOPS charging stops and save in agent
        """
        self.valid_patterns = []
        valid_stops = set()
        valid_fast_stops = set()

        if zero_break:
            stop = self.schedule[0]
            bp = (float(stop["sx"]), float(stop["sy"]))
            add_valid_stop(0, bp, breakpoints_filter, valid_stops, valid_fast_stops)

        for index, stop in enumerate(self.schedule):
            bp = (float(stop["ex"]), float(stop["ey"]))
            add_valid_stop(
                index + 1, bp, breakpoints_filter, valid_stops, valid_fast_stops
            )

        stop_combinations = [
            tuple(
                [
                    2 if k in fast_charge_set else 1 if k in charge_set else 0
                    for k in range(self.num_stops)
                ]
            )
            for num_charges in range(MAX_EXACT_STOPS + 1)
            for charge_set in itertools.combinations(valid_stops, num_charges)
            for num_fast_charges in range(
                len(valid_fast_stops.intersection(set(charge_set))) + 1
            )
            for fast_charge_set in itertools.combinations(
                valid_fast_stops.intersection(set(charge_set)), num_fast_charges
            )
        ]

        while stop_combinations:
            combination = stop_combinations.pop(0)
            if not self.is_valid_pattern(combination):
                continue
            self.valid_patterns += [combination]
            dominated = []
            for c in stop_combinations:
                if all([x[0] <= x[1] for x in zip(combination, c)]):
                    dominated.append(c)

            for c in dominated:
                stop_combinations.pop(stop_combinations.index(c))

    def calculate_greedy_pattern(
        self, breakpoints_filter, start_pattern=[], zero_break=True
    ):
        """
        calculate greedy pattern with respect to some starting pattern
        return greedy pattern or False if there is none
        """
        valid_stops = set()
        valid_fast_stops = set()

        if zero_break:
            stop = self.schedule[0]
            bp = (float(stop["sx"]), float(stop["sy"]))
            add_valid_stop(0, bp, breakpoints_filter, valid_stops, valid_fast_stops)

        for index, stop in enumerate(self.schedule):
            bp = (float(stop["ex"]), float(stop["ey"]))
            add_valid_stop(
                index + 1, bp, breakpoints_filter, valid_stops, valid_fast_stops
            )

        if not self.is_valid_pattern(
            start_pattern
            + [
                2 if i in valid_fast_stops else 1 if i in valid_stops else 0
                for i in range(len(start_pattern), self.num_stops)
            ]
        ):
            return False

        greedy_pattern = start_pattern + [
            2 if i in valid_fast_stops else 1 if i in valid_stops else 0
            for i in range(len(start_pattern), self.num_stops)
        ]
        for i in range(self.num_stops - 1, len(start_pattern) - 1, -1):
            if self.is_valid_pattern(
                [0 if index == i else g for index, g in enumerate(greedy_pattern)]
            ):
                greedy_pattern[i] = 0
            elif i in valid_stops and self.is_valid_pattern(
                [1 if index == i else g for index, g in enumerate(greedy_pattern)]
            ):
                greedy_pattern[i] = 1
        return tuple(greedy_pattern)
