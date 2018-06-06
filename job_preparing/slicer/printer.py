class Printer:
    width = 2560
    height = 1600
    pixel = 0.0076
    
    @property
    def width_mm(self):
        return self.width * self.pixel
        
    @property
    def height_mm(self):
        return self.height * self.pixel


printer = Printer()

