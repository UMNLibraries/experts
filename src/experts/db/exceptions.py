class ExpertsDbException(Exception):
    '''Base class for experts.db exceptions.'''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
