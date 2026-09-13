import numpy as np



def _load_pygame():
    try:
        import pygame
    except ModuleNotFoundError as error:
        raise ImportError("Visualization requires pygame; install darpy[visualization]") from error
    return pygame


def _display_dimensions(shape):
    """Scale both grid axes together without a scikit-learn dependency."""
    if len(shape) != 2 or min(shape) <= 0:
        raise ValueError("visualization requires a nonempty two-dimensional grid")
    scale = 800 / max(shape)
    return tuple(max(1, round(axis * scale)) for axis in shape)

# CONSTANTS:
BLACK = (0, 0, 0)
GREY = (160, 160, 160)

class visualize_paths():
    def __init__(self, AllRealPaths, subCellsAssignment, DroneNo, color):
        self._pygame = _load_pygame()
        self.AllRealPaths = AllRealPaths
        self.subCellsAssignment = subCellsAssignment
        self.dimensions = _display_dimensions(self.subCellsAssignment.shape)

        self.DroneNo = DroneNo
        self._VARS = {'surf': False,
                      'gridWH': (self.dimensions[0], self.dimensions[1]),
                      'gridOrigin': (0, 0),
                      'gridCellsX': self.subCellsAssignment.shape[0],
                      'gridCellsY': self.subCellsAssignment.shape[1],
                      'lineWidth': 2}
        self.color = color

    def visualize_paths(self, mode):
        self._pygame.init()
        self._VARS['surf'] = self._pygame.display.set_mode((self.dimensions[1], self.dimensions[0]))
        self._pygame.display.set_caption('Mode: ' + str(mode))
        while True:
            keep_going = self.checkEvents()
            if not keep_going:
                break
            self._VARS['surf'].fill(GREY)
            self.drawSquareGrid(self._VARS['gridOrigin'],
                                self._VARS['gridWH'],
                                self._VARS['gridCellsX'],
                                self._VARS['gridCellsY'])
            self.placeCells()
            self._pygame.display.update()

    def placeCells(self):
        cellBorder = 0
        celldimX = (self._VARS['gridWH'][0]/self._VARS['gridCellsX'])
        celldimY = (self._VARS['gridWH'][1]/self._VARS['gridCellsY'])
        
        for r in range(self.DroneNo):
            for point in self.AllRealPaths[r]:
                color = self._pygame.Color(255, 0, 0)
                self._pygame.draw.line(self._VARS['surf'],
                                 self.color[r],
                                 (self._VARS['gridOrigin'][0] + (celldimX*point[1] + celldimX/2),
                                  self._VARS['gridOrigin'][1] + (celldimY*point[0]) + celldimY/2),
                                 (self._VARS['gridOrigin'][0] + (celldimX*point[3]) + celldimX/2,
                                  self._VARS['gridOrigin'][1] + (celldimY*point[2]) + celldimY/2), width=4)

        cellBorder = 0

        for row in range(self.subCellsAssignment.shape[0]):
            for column in range(self.subCellsAssignment.shape[1]):
                if (self.subCellsAssignment[row][column] == self.DroneNo):
                    self.drawSquareCell(
                        self._VARS['gridOrigin'][0] + (celldimX*column)
                        + self._VARS['lineWidth']/2,
                        self._VARS['gridOrigin'][1] + (celldimY*row)
                        + self._VARS['lineWidth']/2,
                        celldimX, celldimY, BLACK)

    # Draw filled rectangle at coordinates
    def drawSquareCell(self, x, y, dimX, dimY, color):
        self._pygame.draw.rect(
         self._VARS['surf'], color,
         (x, y, dimX, dimY)
        )

    def drawSquareGrid(self, origin, gridWH, cellsX, cellsY):
        CONTAINER_WIDTH_HEIGHT = gridWH
        cont_x, cont_y = (0, 0)

        # DRAW Grid Border:
        # TOP lEFT TO RIGHT
        self._pygame.draw.line(
          self._VARS['surf'], BLACK,
          (cont_x, cont_y),
          (CONTAINER_WIDTH_HEIGHT[1] + cont_x, cont_y), self._VARS['lineWidth'])

        # # BOTTOM lEFT TO RIGHT
        self._pygame.draw.line(
          self._VARS['surf'], BLACK,
          (cont_x, CONTAINER_WIDTH_HEIGHT[0] + cont_y),
          (CONTAINER_WIDTH_HEIGHT[1] + cont_x,
           CONTAINER_WIDTH_HEIGHT[0] + cont_y), self._VARS['lineWidth'])

        # # LEFT TOP TO BOTTOM
        self._pygame.draw.line(
          self._VARS['surf'], BLACK,
          (cont_x, cont_y),
          (cont_x, cont_y + CONTAINER_WIDTH_HEIGHT[0]), self._VARS['lineWidth'])
        # # RIGHT TOP TO BOTTOM
        self._pygame.draw.line(
          self._VARS['surf'], BLACK,
          (CONTAINER_WIDTH_HEIGHT[1] + cont_x, cont_y),
          (CONTAINER_WIDTH_HEIGHT[1] + cont_x,
           CONTAINER_WIDTH_HEIGHT[0] + cont_y), self._VARS['lineWidth'])

        # Get cell size, just one since its a square grid.
        cellSizeX = CONTAINER_WIDTH_HEIGHT[0]/cellsX
        cellSizeY = CONTAINER_WIDTH_HEIGHT[1]/cellsY

        for x in range(cellsY):
            self._pygame.draw.line(
               self._VARS['surf'], BLACK,
               (cont_x + (cellSizeX * x), cont_y),
               (cont_x + (cellSizeX * x), CONTAINER_WIDTH_HEIGHT[0] + cont_y), 2)
        for y in range(cellsX):
        # # HORIZONTAl DIVISIONS
            self._pygame.draw.line(
              self._VARS['surf'], BLACK,
              (cont_x, cont_y + (cellSizeY*y)),
              (cont_x + CONTAINER_WIDTH_HEIGHT[1], cont_y + (cellSizeY*y)), 2)

    def checkEvents(self):
        for event in self._pygame.event.get():
            if event.type == self._pygame.QUIT or (event.type == self._pygame.KEYDOWN and event.key == self._pygame.K_q):
                self._pygame.quit()
                return False
        return True


class darp_area_visualization(object):
    def __init__(self, Assignment_matrix, DroneNo, color, init_robot_pos):
        self._pygame = _load_pygame()
        self.Assignment_matrix = Assignment_matrix
        dimensions = _display_dimensions(self.Assignment_matrix.shape)

        self.DroneNo = DroneNo
        self._VARS = {'surf': False,
                      'gridWH': (dimensions[0], dimensions[1]),
                      'gridOrigin': (0, 0),
                      'gridCellsX': self.Assignment_matrix.shape[0],
                      'gridCellsY': self.Assignment_matrix.shape[1],
                      'lineWidth': 2}
        self.color = color
        self.init_robot_pos_colors = [np.clip((r[0] - 20, r[1] + 20, r[2] - 20), 0, 255).tolist() for r in self.color]
        self.init_robot_pos = init_robot_pos
        self._pygame.init()
        self._VARS['surf'] = self._pygame.display.set_mode((dimensions[1], dimensions[0]))
        self.checkEvents()
        self._VARS['surf'].fill(GREY)
        self.drawSquareGrid(self._VARS['gridOrigin'], self._VARS['gridWH'], 
                            self._VARS['gridCellsX'], self._VARS['gridCellsY'])
        self.placeCells(self.Assignment_matrix)
        self._pygame.display.set_caption('Assignment Matrix')
        self._pygame.display.update()
        # time.sleep(5)

    def checkEvents(self):
        for event in self._pygame.event.get():
            if event.type == self._pygame.QUIT or (event.type == self._pygame.KEYDOWN and event.key == self._pygame.K_q):
                self._pygame.quit()
                raise InterruptedError("coverage visualization closed")

    def drawSquareGrid(self, origin, gridWH, cellsX, cellsY):
        CONTAINER_WIDTH_HEIGHT = gridWH
        cont_x, cont_y = (0, 0)

        # DRAW Grid Border:
        # TOP lEFT TO RIGHT
        self._pygame.draw.line(
          self._VARS['surf'], BLACK,
          (cont_x, cont_y),
          (CONTAINER_WIDTH_HEIGHT[1] + cont_x, cont_y), self._VARS['lineWidth'])

        # # BOTTOM lEFT TO RIGHT
        self._pygame.draw.line(
          self._VARS['surf'], BLACK,
          (cont_x, CONTAINER_WIDTH_HEIGHT[0] + cont_y),
          (CONTAINER_WIDTH_HEIGHT[1] + cont_x,
           CONTAINER_WIDTH_HEIGHT[0] + cont_y), self._VARS['lineWidth'])

        # # LEFT TOP TO BOTTOM
        self._pygame.draw.line(
          self._VARS['surf'], BLACK,
          (cont_x, cont_y),
          (cont_x, cont_y + CONTAINER_WIDTH_HEIGHT[0]), self._VARS['lineWidth'])
        # # RIGHT TOP TO BOTTOM
        self._pygame.draw.line(
          self._VARS['surf'], BLACK,
          (CONTAINER_WIDTH_HEIGHT[1] + cont_x, cont_y),
          (CONTAINER_WIDTH_HEIGHT[1] + cont_x,
           CONTAINER_WIDTH_HEIGHT[0] + cont_y), self._VARS['lineWidth'])

        # Get cell size, just one since its a square grid.
        cellSizeX = CONTAINER_WIDTH_HEIGHT[0]/cellsX
        cellSizeY = CONTAINER_WIDTH_HEIGHT[1]/cellsY

        for x in range(cellsY):
            self._pygame.draw.line(
               self._VARS['surf'], BLACK,
               (cont_x + (cellSizeX * x), cont_y),
               (cont_x + (cellSizeX * x), CONTAINER_WIDTH_HEIGHT[0] + cont_y), 2)
        for y in range(cellsX):
        # # HORIZONTAl DIVISIONS
            self._pygame.draw.line(
              self._VARS['surf'], BLACK,
              (cont_x, cont_y + (cellSizeY*y)),
              (cont_x + CONTAINER_WIDTH_HEIGHT[1], cont_y + (cellSizeY*y)), 2)

        self._pygame.display.update()
    
    def placeCells(self, Assignment_matrix, iteration_number=0):
        self.checkEvents()
        celldimX = (self._VARS['gridWH'][0]/self._VARS['gridCellsX'])
        celldimY = (self._VARS['gridWH'][1]/self._VARS['gridCellsY'])

        for row in range(self.Assignment_matrix.shape[0]):
            for column in range(self.Assignment_matrix.shape[1]):
                if (self.Assignment_matrix[row][column] == self.DroneNo):
                    self.drawSquareCell(
                        self._VARS['gridOrigin'][0] + (celldimX*column)
                        + self._VARS['lineWidth']/2,
                        self._VARS['gridOrigin'][1] + (celldimY*row)
                        + self._VARS['lineWidth']/2,
                        celldimX, celldimY, BLACK)
                    continue
                for r in range(self.DroneNo):
                    if self.init_robot_pos[r] == (row, column):
                        self.drawSquareCell(
                            self._VARS['gridOrigin'][0] + (celldimX * column)
                            + self._VARS['lineWidth'] / 2,
                            self._VARS['gridOrigin'][1] + (celldimY * row)
                            + self._VARS['lineWidth'] / 2,
                            celldimX, celldimY, self.init_robot_pos_colors[r])
                        continue
                    else:
                        if self.Assignment_matrix[row][column] == r:
                            self.drawSquareCell(
                                self._VARS['gridOrigin'][0] + (celldimX*column)
                                + self._VARS['lineWidth']/2,
                                self._VARS['gridOrigin'][1] + (celldimY*row)
                                + self._VARS['lineWidth']/2,
                                celldimX, celldimY, self.color[r])
       
        self.drawSquareGrid(self._VARS['gridOrigin'], self._VARS['gridWH'], 
                            self._VARS['gridCellsX'], self._VARS['gridCellsY'])
        
        self._pygame.display.set_caption('Assignment Matrix [Iteration: ' + str(iteration_number) + ']')
        self._pygame.display.update()

    def drawSquareCell(self, x, y, dimX, dimY, color):
        self._pygame.draw.rect(
         self._VARS['surf'], color,
         (x, y, dimX, dimY)
        )
