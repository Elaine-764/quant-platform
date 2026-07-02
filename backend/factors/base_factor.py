class Factor:
    def compute(self, data, t=None):
        raise NotImplementedError
    
    def output_column(self, t=None): # column name
        raise NotImplementedError