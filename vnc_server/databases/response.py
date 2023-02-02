"""
With the the following layer hierarchy in mind:
 - Logic
 - Utility
 - Driver Wrapper (NeoDB)
 - Driver

Functions in the Utility layer return a Response to the Logic layer.

Note that the Driver Wrapper layer (NeoDB) simply returns
a list of paths to the Utility layer.

"""


class Response(object):
    """
    This class represents 
    """
    def __init__(self, success, message, results=None):
        assert isinstance(success, bool), 'Success must be a bool'
        assert isinstance(message, str),  'Message must be a str'
        if (results is not None):
            assert isinstance(results, list) \
                or isinstance(results, dict), 'Results must be a list or dict'

        self.success = success
        self.message = message
        self.results = results

    def __str__(self):
        out = ''

        out += '[Response {'

        out += 'success: %s, ' % self.success
        out += 'message: \'%s\', ' % self.message
        out += 'results: %s' % self.results

        out += '}]'

        return out

