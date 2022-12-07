from .const import(
    MIN_X,
    MIN_Y
)

import csv
import numpy as np

def pointToCell(x,y):
    return (int((x - MIN_X)/100),int((y - MIN_Y)/100))
    
def cellToPoint(x,y):
    return (MIN_X+100*(x+0.5),MIN_Y+100*(y+0.5))

def findAllCells(position_file):
    cells = {}
    tmpCells = csv.DictReader(open(position_file, mode="r"))
    for cell in tmpCells:
        c = (int(cell["cx"]),int(cell["cy"]))
        cells[c]=cellToPoint(*c)
    return cells

#filters cells that are relevant for our given problem
def filterCells(potentialCells,breakpoints,radius=200,deleteDuplicates=True):
    comb_radius=radius//100
    relevantCells = {key:set() for key in potentialCells}
    for bp in breakpoints:
        cell = pointToCell(*bp)
        candidates = [(cell[0]+2-i,cell[1]+2-j)for i in range(2*comb_radius+1) for j in range(2*comb_radius+1)]
        for c in candidates:
            if c in potentialCells:
                if np.linalg.norm(np.array(bp)-np.array((potentialCells[c])))<=radius:
                    relevantCells[c].add(bp)

    if deleteDuplicates:
        reducedCells = {}
        for cell,rbps in relevantCells.items():
            b_maximal = True
            keysToDelete = []
            for r_cell,r_rbps in reducedCells.items():
                if r_rbps.issubset(rbps):
                    keysToDelete.append(r_cell)
                elif rbps.issubset(r_rbps):
                    b_maximal = False
                    break
            
            for key in keysToDelete:
                del reducedCells[key]

            if b_maximal:
                reducedCells[cell]=rbps
    else:
        reducedCells=relevantCells

    return reducedCells

def findRelevantCellsForBreakpoints(breakpoints,cells):
    neighboringCells = {}
    for bp in breakpoints:
        neighboringCells[bp] = []
        for cell in cells:
            if bp in cells[cell]:
                neighboringCells[bp].append(cell)
    return neighboringCells