class PureWebServicesException(Exception):
    '''Base class for experts.pure.web_services exceptions.client.'''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
