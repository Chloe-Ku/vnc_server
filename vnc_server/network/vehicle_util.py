#
# Contains classes with useful functions for handling vehicle/server communication.
#

import math
import json
from enum import Enum
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from dijkstar import Graph, find_path

from vehicle import Vehicle

from typing import Tuple, Optional

# Hacky work-around to be able to import from a folder above this one.
import sys
import os

#sys.path.append(os.path.abspath('../databases'))
#from sqldb import SQLDB

sys.path.append(os.path.abspath('../../vnc_client/scripts'))
import googlemaps_util

#WAIT_TIME = 180000 #TODO: This code is for a possible auto-confirm pickup/arrival after a time-out. I am not sure this is needed.

class State(Enum):
    IDLE = 1
    TO_RIDER = 2
    TO_DEST = 3
    ENROUTE_TO_RIDER = 4
    ENROUTE_TO_DEST = 5
    ENROUTE_TO_CHARGER = 6
    CHARGING = 7


class FSMUtil(object):
    @staticmethod
    def expectClass(obj, theClass):
        if (obj.__class__ != theClass):
            errStr = 'Expected %s; Got: %s. ' % (
                theClass.__name__, obj.__class__.__name__)
            raise Exception(errStr)


class SpatialUtil(object):
    @staticmethod
    def getDist(lat1, lon1, lat2, lon2):
        dLat = lat2 - lat1
        dLon = lon2 - lon1
        avgLat = (lat1 + lat2) / 2.0
        dY = (10000000.0 / 90.0) * dLat
        dX = (10000000.0 / 90.0) * dLon * math.cos(math.radians(avgLat))

        return math.sqrt((dX*dX) + (dY*dY))

    @staticmethod
    def getSpeed(maxSpeed, curLat, curLon, toLat, toLon):
        dist = SpatialUtil.getDist(curLat, curLon, toLat, toLon)

        if (dist > Vehicle.startSlowingDist):
            return maxSpeed

        return maxSpeed * (dist / Vehicle.startSlowingDist)

    def atCoords(curLat, curLon, toLat, toLon):
        dist = SpatialUtil.getDist(curLat, curLon, toLat, toLon)

        return dist <= Vehicle.proximityAllowed


class PathUtil(object):
    def shortestPath(graph, startNode, endNode):
        g = Graph()

        edgeMap = graph['edges']
        for edgeName in edgeMap:
            edge = edgeMap[edgeName]

            # Make it 'undirected' from a directed representation
            g.add_edge(edge['vertex1'], edge['vertex2'],
                       {'cost': edge['distance']})
            g.add_edge(edge['vertex2'], edge['vertex1'],
                       {'cost': edge['distance']})

        def cost_func(u, v, e, prev_e): return e['cost']

        nodeList = find_path(g, startNode, endNode, cost_func=cost_func).nodes

        vertexMap = graph['vertices']
        return [vertexMap[n] for n in nodeList]

class VehicleDBUtil(object):
    @staticmethod
    def registerVehicle(db, initRequest):
        print('registerVehicle(%s)' % initRequest)

        # Get the vehicle (if it exists)
        whereObj = {
            'name': initRequest.name
        }
        response = db.read('Vehicles', ['name'], ['name'], whereObj)
        if (response.success != True):
            print('Failed to read for vehicle existence: %s' %
                  response.message)
            return False

        if (len(response.results) > 0):
            # Just update, because it already exists
            setAttrs = {
                'lat':         initRequest.lat,
                'lon':         initRequest.lon,
                'batteryLife': initRequest.batteryLife,
                'enabled': 1
            }
            whereAttrs = {
                'name': initRequest.name
            }
            response = db.update('Vehicles', setAttrs, whereAttrs)
            if (response.success != True):
                print('Failed to update vehicle: %s' % response.message)
                return False
        else:
            # Just insert, because it doesn't exist yet
            obj = {
                'name':        initRequest.name,
                'lat':         initRequest.lat,
                'lon':         initRequest.lon,
                'batteryLife': initRequest.batteryLife,
                'enabled':     1
            }
            cols = list(obj.keys())
            response = db.create('Vehicles', cols, obj)
            if (response.success != True):
                print('Failed to create vehicle: %s' % response.message)
                return False

        return True

    @staticmethod
    def updateStatus(db, vName: str, status: str, t: int, lat: float, lon: float, batLife: int = -1,
                       curRideId: Optional[int] = -1) -> bool:
        """Insterts the vehicle's location and status into CoordHistory table

        The status should be one of the given list:
        ('WAITING', 'ENROUTE_TO_RIDER', 'TO_RIDER', 'ENROUTE_TO_DEST', 'TO_DEST').

        Beware that the time 't' is used as primary key. So, if you try to report
        the location more than once per second, the insertion will fail. So, instead,
        the already existing entry will be updated with new information.

        :param db: the reference to the db interface instance. Normally :class:`vnc_server.databases.sqldb.SQLDB`
        :type db: :class:`vnc_server.databases.sqldb.SQLDB`
        :param vName: the name of the vehicle
        :type vName: str
        :param status: the status of the vehicle
        :type status: str
        :param t: the time associated with the given information
        :type t: int
        :param lat: the latitude of the vehicle
        :type lat: float
        :param lon: the longitude of the vehicle
        :type lon: float
        :param batLife: the battery life of the vehicle. Defaults to -1 if this should not be reported
        :type: int
        :param curRideId: the ride id associated with the vehicle. Defaults to -1 if this should not be reported.
                          For the cases when the ride id should be set to NULL (when ride is finished or canceled)
                          provide None.
        :type: None or int
        :return: True if the info was successfuly added to the table or False otherwise
        :rtype: bool
        """
        wasSuccessful = True

        #
        # Update the coordinate history
        #
        obj = {
            'vehicleName': vName,
            'status':      status,
            't':           t,
            'lat':         lat,
            'lon':         lon
        }
        cols = list(obj.keys())
        response = db.create('CoordHistory', cols, obj)
        if not response.success:
            if "Duplicate entry" not in response.message:
                print('Failed to insert into CoordinateHistory: %s' %
                    response.message)
                wasSuccessful = False
            else:
                setAttrs = {
                    'lat': lat,
                    'lon': lon,
                    'status': status
                }
                whereAttrs = {
                    'vehicleName': vName,
                    't': t
                }
                response = db.update('CoordHistory', setAttrs, whereAttrs)
                if (response.success != True):
                    print('Failed to update Vehicle coordinates in CoordHistory: %s' %
                        response.message)
                    wasSuccessful = False

        #
        # Update vehicle's status
        #
        setAttrs = {
            'lat': lat,
            'lon': lon,
            'status': status
        }

        if batLife != -1:
            setAttrs["batteryLife"] = batLife
        if curRideId is None or curRideId != -1:
            setAttrs["curRideID"] = curRideId

        whereAttrs = {
            'name': vName,
        }
        response = db.update('Vehicles', setAttrs, whereAttrs)
        if (response.success != True):
            print('Failed to update Vehicle coordinates: %s' %
                response.message)
            wasSuccessful = False

        return wasSuccessful

    @staticmethod
    def disableVehicle(db, name):
        setAttrs = {
            'enabled': 0
        }
        whereAttrs = {
            'name': name
        }
        response = db.update('Vehicles', setAttrs, whereAttrs)
        if (response.success != True):
            print('Failed to update vehicle: %s' % response.message)
            return False
        else:
            return True

    @staticmethod
    def getVehicles(db, enabled_only: bool=True) -> Tuple[dict]:
        """Returns the tuple of the dicts representing :class:`Vehicle` from the Vehicles table

        By default returns only enabled vehicles.
        In case of error returns empty tuple.
        The tuple contains dicts that represent the fields of the Vehicle class.

        :param db: the instance of the database interface to use. Typically :class:`vnc_server.databases.sqldb.SQLDB`
        :type db: `vnc_server.databases.sqldb.SQLDB`
        :param enabled_only: the flag indicating whether the disabled vehicles should also be included in the tuple of vehicles.
                             Defaults to True
        :type enabled_only: bool
        :return: the tuple of vehicles
        :rtype: Tuple[dict]
        """
        if enabled_only:
            response = db.read('Vehicles', '*', ['enabled'], {'enabled': True})
        else:
            response = db.read('Vehicles', '*', [], {})
        if not response.success:
            print('Failed to retrieve Vehicles: %s' % response.message)
            return ()
        return tuple(response.results)

    @staticmethod
    def getVehiclesLite(db, enabled_only: bool=True) -> Tuple[dict]:
        """Returns the tuple of the dicts representing :class:`Vehicle` from the Vehicles table
        Only the lat, lon, status and name.

        By default returns only enabled vehicles.
        In case of error returns empty tuple.
        The tuple contains dicts that represent the fields of the Vehicle class.

        :param db: the instance of the database interface to use. Typically :class:`vnc_server.databases.sqldb.SQLDB`
        :type db: `vnc_server.databases.sqldb.SQLDB`
        :param enabled_only: the flag indicating whether the disabled vehicles should also be included in the tuple of vehicles.
                             Defaults to True
        :type enabled_only: bool
        :return: the tuple of vehicles, only the lat, lon, status and name
        :rtype: Tuple[dict]
        """
        if enabled_only:
            response = db.read('Vehicles', ['name', 'status', 'lat', 'lon'], ['enabled', 'status'], {'enabled': True, 'status': 'WAITING'})
        else:
            response = db.read('Vehicles', ['name', 'status', 'lat', 'lon'], [], {})
        if not response.success:
            print('Failed to retrieve Vehicles: %s' % response.message)
            return ()
        return tuple(response.results)

    @staticmethod
    def getChargerNode(db):
        whereObj = {
            'id': 2
        }
        response = db.read('LocationNodes', ['lat', 'lon'], ['id'], whereObj)
        if (response.success != True):
            print('Failed to read for LocationNodes: %s' %
                  response.message)
            return None
        if (len(response.results) < 1):
            print('No Node with this id')
            return None
        if (len(response.results) > 1):
            print('Constraint failure: more than one Node with this id')
            return None
        return response.results[0]["lat"], response.results[0]["lon"]

    @staticmethod
    def getLocationNodes(db):
        """Returns a list of all of the locationNodes

        Get all the location nodes in the database.

        :param db: the instance of the database interface to use. Typically :class:`vnc_server.databases.sqldb.SQLDB`
        :type db: `vnc_server.databases.sqldb.SQLDB`
        """

        response = db.read('LocationNodes', ['nodeName', 'lat', 'lon'], [], {})
        if (response.success != True):
            print('Failed to read for LocationNodes: %s' %
                  response.message)
            return None
        if (len(response.results) < 1):
            print('No location nodes')
            return None
        return tuple(response.results)

    @staticmethod
    def getVehicleLocation(db, vName):
        """Returns the latitude and longitude of the vehichle

        Given the vehichle name, returns the lat,lon of vehichle

        :param db: the instance of the database interface to use. Typically :class:`vnc_server.databases.sqldb.SQLDB`
        :type db: `vnc_server.databases.sqldb.SQLDB`
        :param vName: name of the vehichle
        :type vName: str
        :return: lat, lon of vehichle
        :rtype: str,str
        """
        whereObj = {
            'name': vName
        }
        response = db.read('Vehicles', ['lat', 'lon'], ['name'], whereObj)
        if (response.success != True):
            print('Failed to read for Vehicle: %s' %
                  response.message)
            return None
        if (len(response.results) < 1):
            print('No Vehicle with this name')
            return None
        if (len(response.results) > 1):
            print('Constraint failure: more than one Vehicle with this name')
            return None
        return response.results[0]["lat"], response.results[0]["lon"]

class RideDBUtil(object):

    #WAIT_TIME = 20000 #TODO: This code is for a possible auto-confirm pickup/arrival after a time-out

    @staticmethod
    def addRide(db, newRide):
        #TODO: Add rideID return
        obj = {
            'userEmail' : newRide.getRiderEmail(),
            'tStart' : newRide.getTime(),
            'startNode' : str(newRide.getRiderLocation()),
            'endNode' : str(newRide.getDestLocation())
        }
        cols = list(obj.keys())
        response = db.create('Rides', cols, obj)
        if not response.success:
            print('Failed to create a new Ride: %s' % response.message)
            return False
        return True

    @staticmethod
    def getRideID(db, riderEmail):
        whereObj = {
            'userEmail': riderEmail
        }
        response = db.read('Rides', ['userEmail', 'id'], ['userEmail'], whereObj)
        if (response.success != True):
            print('Failed to read for ride existence: %s' %
                  response.message)
            return None
        if (len(response.results) < 1):
            print('No ride with this email')
            return None
        if (len(response.results) > 1):
            print('Constraint failure: more than one ride with this email')
            return None
        return response.results[0]["id"]

    @staticmethod
    def getUserRide(db, riderEmail):
        whereObj = {
            'userEmail': riderEmail
        }
        response = db.read('Rides', ['userEmail', 'id', 'pickedUp', 'arrived', 'canceled', 'startNode', 'endNode'], ['userEmail'], whereObj)
        if (response.success != True):
            print('Failed to read for ride existence: %s' %
                  response.message)
            return None
        if (len(response.results) < 1):
            print('No ride with this email')
            return None
        if (len(response.results) > 1):
            print('Constraint failure: more than one ride with this email')
            return None
        return response.results[0]

    @staticmethod
    def getRides(db) -> Tuple[dict]:
        """Returns the tuple of the dicts representing :class:`Ride` from the Rides table

        Returns a tuple of pending rides. Does not return Rides that have been completed.
        The cancelled rides will be returned only if the vehicle is reaching the target
        safe point at the moment of request.
        In case of error returns empty tuple.
        The tuple contains dicts that represent the fields of the Rides class.

        :param db: the instance of the database interface to use. Typically :class:`vnc_server.databases.sqldb.SQLDB`
        :type db: `vnc_server.databases.sqldb.SQLDB`
        :return: the tuple of pending rides
        :rtype: Tuple[dict]
        """
        response = db.read('Rides', '*', [], {})
        if not response.success:
            print('Failed to retrieve Rides: %s' % response.message)
            return ()
        return tuple(response.results)

    @staticmethod
    def getRide(db, rideID):
        # Get the ride (if it exists)
        whereObj = {
            'id': rideID
        }
        response = db.read('Rides', ['id', 'status', 'tStart', 'startNode', 'endNode', 'pickedUp', 'arrived', 'canceled', 'userEmail', 'vehicleName'], ['id'], whereObj)
        if (response.success != True):
            print('Failed to read for ride existence: %s' %
                  response.message)
            return None

        return response.results[0]

    @staticmethod
    def getUser(db, email):
        # Get the ride (if it exists)
        whereObj = {
            'email': email
        }
        response = db.read('Users', ['email', 'fname', 'lname', 'type', 'salt', 'hash', 'extID', 'extType', 'authToken', 'token_expiration', 'curRideID'], ['email'], whereObj)
        if (response.success != True):
            print('Failed to read for user existence: %s' %
                  response.message)
            return None

        if (len(response.results) == 0):
            print('Failed to read for user existence: %s' %
                  response.message)
            return None

        return response.results[0]

    @staticmethod
    def getVehicle(db, rideID):
        """Returns the lat and lon of the vehicle associated with the given ride.
        """
        # Get the vehicle (if it exists)
        whereObj = {
            'id': rideID
        }
        print('vehicle_util:486')
        print(rideID)
        response = db.read('Rides', ['id', 'status', 'tStart', 'startNode', 'endNode', 'pickedUp', 'arrived', 'canceled', 'userEmail', 'vehicleName'], ['id'], whereObj)
        
        if (response.success != True):
            print('Failed to read for ride existence: %s' %
                  response.message)
            return None

        vehicleName = response.results[0]['vehicleName']
        # If the vehicle exists, try to return the coordinates of it
        if (vehicleName):
            whereObj = {
                'name': vehicleName
            }
            response = db.read('Vehicles', ['name', 'status', 'lat', 'lon'], ['name'], whereObj)
            if (response.success != True):
                print('Failed to read for Vehicle: %s' %
                    response.message)
                return None
            if (len(response.results) < 1):
                print('No Vehicle with this name')
                return None
            if (len(response.results) > 1):
                print('Constraint failure: more than one Vehicle with this name')
                return None
            return response.results[0]
        print('Ride has no vehicle')
        return None

    @staticmethod
    def confirmPickup(db, rideID):
        # Get the ride (if it exists)
        whereObj = {
            'id': rideID
        }
        response = db.read('Rides', ['id'], ['id'], whereObj)


        if (response.success != True):
            print('Failed to read for ride existence: %s' %
                  response.message)
            return False

        if (len(response.results) > 0):
            # Ride exists, update pickedUp field
            setAttrs = {
                'pickedUp':         1
            }
            whereAttrs = {
                'id': rideID
            }
            response = db.update('Rides', setAttrs, whereAttrs)
            if (response.success != True):
                print('Failed to update ride: %s' % response.message)
                return False
        else:
            # No ride with this id
            print('The ride specified does not exist')
            return False

        return True

    @staticmethod
    def checkPickupConfirmation(db, rideID):
        # Get the ride (if it exists)
        whereObj = {
            'id': rideID
        }
        ride = db.read('Rides', ['id', 'pickedUp'], ['id'], whereObj)
        if (ride.success != True):
            print('Failed to read for ride existence: %s' %
                  ride.message)
            return None
        return (ride.results[0]['pickedUp'] == '\x01')

    @staticmethod
    def confirmArrival(db, rideID):
        # Get the ride (if it exists)
        whereObj = {
            'id': rideID
        }
        response = db.read('Rides', ['id'], ['id'], whereObj)


        if (response.success != True):
            print('Failed to read for ride existence: %s' %
                  response.message)
            return False

        if (len(response.results) > 0):
            # Ride exists, update arrived field
            setAttrs = {
                'arrived':         1
            }
            whereAttrs = {
                'id': rideID
            }
            response = db.update('Rides', setAttrs, whereAttrs)
            if (response.success != True):
                print('Failed to update ride: %s' % response.message)
                return False
        else:
            # No ride with this id
            print('The ride specified does not exist')
            return False

        return True

    @staticmethod
    def checkArrivalConfirmation(db, rideID):
        # Get the ride (if it exists)
        whereObj = {
            'id': rideID
        }
        ride = db.read('Rides', ['id', 'arrived'], ['id'], whereObj)
        if (ride.success != True):
            print('Failed to read for ride existence: %s' %
                  ride.message)
            return None
        return (ride.results[0]['arrived'] == '\x01')

    @staticmethod
    def cancelRide(db, rideID):
        # Get the ride (if it exists)
        whereObj = {
            'id': rideID
        }
        response = db.read('Rides', ['id'], ['id'], whereObj)


        if (response.success != True):
            print('Failed to read for ride existence: %s' %
                  response.message)
            return False

        if (len(response.results) > 0):
            # Ride exists, update canceled field
            setAttrs = {
                'canceled':         1
            }
            whereAttrs = {
                'id': rideID
            }
            response = db.update('Rides', setAttrs, whereAttrs)
            if (response.success != True):
                print('Failed to update ride: %s' % response.message)
                return False
        else:
            # No ride with this id
            print('The ride specified does not exist')
            return False

        return True

    @staticmethod
    def checkCanceled(db, rideID):
        # Get the ride (if it exists)
        whereObj = {
            'id': rideID
        }
        ride = db.read('Rides', ['id', 'canceled'], ['id'], whereObj)
        if (ride.success != True):
            print('Failed to read for ride existence: %s' %
                  ride.message)
            return None
        return (ride.results[0]['canceled'] == '\x01')

    @staticmethod
    def getRideHistory(db, email):
        whereObj = {
            'userEmail': email
        }
        response = db.read('RideHistory', ['id', 'userEmail', 'vehicleName', 'tStart', 'tEnd', 'startNode', 'endNode'], whereObj.keys(), whereObj)
        if (response.success != True):
            print('Failed to get ride history: %s' %
                  response.message)
            return None
        return response.results

    @staticmethod
    def getLocationNodeByCoordinates(db, coordinates):
        coordinates = coordinates[1:-1].split(', ')
        whereObj = {
            'lat': coordinates[0],
            'lon': coordinates[1]
        }
        response = db.read('LocationNodes', ['nodeName'], whereObj.keys(), whereObj)
        if (response.success != True):
            print('Failed to get LocationNode from given coordinates: %s' %
                  response.message)
            return None
        return response.results[0]['nodeName']

class CoolFunctions(object):
    """
    Some cool functions (used by VehicleServer for a demo/test).

    Each function maps from time to change in (lat, lon)
    """

    @staticmethod
    def line(t):
        dLat = 5
        dLon = 7

        # print('line(%s) = %s' % (t, (dLat, dLon)))

        return (dLat, dLon)

    @staticmethod
    def circle(t):
        period = 10.0
        radius = 5

        multiplier = (2 * math.pi) / period
        dLat = radius * math.cos(t * multiplier)
        dLon = radius * math.sin(t * multiplier)

        # print('circle(%s) = %s' % (t, (dLat, dLon)))

        return (dLat, dLon)

    @staticmethod
    def wave(t):
        period = 10.0
        amplitude = 1

        multiplier = (2 * math.pi) / period
        dLat = amplitude * math.cos(t * multiplier)
        dLon = 1

        # print('wave(%s) = %s' % (t, (dLat, dLon)))

        return (dLat, dLon)


class Ride():
    """The class representing a ride request

    :param riderEmail: the email of the client requesting a ride
    :type riderEmail: str
    :param riderLat: the latitude of the client's location
    :type riderLat: float
    :param riderLon: the longitude of the client's location
    :type riderLon: float
    :param destLat: the latitude of the client's destination location
    :type destLat: float
    :param destLon: the longitude of the client's destination location
    :type destLon: float
    :param time: the time of the request in seconds
    :type time: float
    """
    def __init__(self, riderEmail: str, riderLat: float, riderLon: float, destLat: float, destLon: float, time: float) -> None:
        self.riderEmail = riderEmail
        self.riderLat = riderLat
        self.riderLon = riderLon
        self.destLat = destLat
        self.destLon = destLon
        self.time = time
        self.rideID = -1

    def getRiderEmail(self) -> str:
        return self.riderEmail

    def getRiderLocation(self) -> Tuple[float, float]:
        return self.riderLat, self.riderLon

    def getDestLocation(self) -> Tuple[float, float]:
        return self.destLat, self.destLon

    def setRideID(self, db) -> None:
        self.rideID = RideDBUtil.getRideID(db, self.riderEmail)

    def getRideID(self) -> int:
        return self.rideID

    def getTime(self) -> float:
        return self.time

    def __str__(self) -> str:
        return f"Ride (email: {self.riderEmail}, rider's location: ({self.riderLat}, {self.riderLat}),"\
               f" destination location: ({self.destLat}, {self.destLat}))"


class VehicleSelectorStrategy(ABC):
    """The abstract class representing a strategy for selecting a ride based on current fleet conditions

    This is an abstract class that serves as basis for all other selection strategies.
    The idea is that the class extending :class:`VehicleSelectorStrategy` provides the concrete implementation of
    :func:`VehicleSelector.selectRide`. This function returns an instance of :class:`vehicle_server.Ride` waiting in the queue
    of requests which matches the given vehicle waiting for an assignment the best based on certain criteria. It can be either
    proximity, battery life, fleet load, riders quantity, etc.

    The class extending this class should indicate that implements certain selection strategy.
    """
    @abstractmethod
    def selectRide(self, vName, queue: List[Ride], **kwargs) -> Optional[Ride]:
        """Selects the Ride instance from a queue of requests that fits current strategy the best

        The concrete implementation should specify which keyword arguments it expects to execute the selection
        strategy. At a minimum it expects a queue of the ride requests.
        Check Keyword Arguments for supported parameters.

        Arguments:
            :param queue: a queue of the ride requests to choose from
            :type queue: list of :class:`vehicle_server.Ride`

        Keyword Arguments:
            :param vehicles: a list of the idle vehicles
            :type vehicles: list of :class:`vehicle.Vehicle`

        :return: instance of Ride request or None if the match was not found
        :rtype: :class:`vehicle_server.Ride`
        """
        pass


class FIFORide(VehicleSelectorStrategy):
    """The basic FIFO selection strategy

    A class representing a FIFO selection. Returns the first ride request waiting in the queue.
    """
    def selectRide(self, vName, queue: List[Ride], **kwargs) -> Optional[Ride]:
        """Selects and returns the first ride request waiting in the queue

        The method does not expect any keyword arguments, so any arguments besides a list of Rides
        will be ignored.

        Arguments:
            :param vName: the vehichle name that is being ride-matched
            :type vName: str of vehichle name
            :param queue: a queue of the ride requests to choose from
            :type queue: list of :class:`vehicle_server.Ride`

        :return: first ride or None if the queue is empty
        :rtype: :class:`vehicle_server.Ride` or None
        """
        try:
            return queue.pop(0)
        except IndexError:
            return None

class ProximityRide(VehicleSelectorStrategy):
    """The ProximityRide selection strategy

    A class representing the Proximity Ride matching algorithm. The algorithm
    checks the first 5 rides in the queue and selects the closest user to
    the avaiable vehichle. It keeps track of how many times a vehichle is
    skipped over. And if a vehichle is skipped 5 times, the next available
    vehichle is matched to this ride.
    """
    def __init__(self) -> None:
        """Constructor method
        """
        self.SKIP_MAX = 5 # How many time we can skip a vehchle in line
        self.NUM_CHECK = 5 # Number of vehichle at the front of the queue to check
        self.rideSkip = {} # keeps track of rides skipped

    def selectRide(self, vName: str, queue: List[Ride], **kwargs) -> Optional[Ride]:
        """Selects and returns the first ride request waiting in the queue

        The method does not expect any keyword arguments, so any arguments besides a list of Rides
        will be ignored.

        Arguments:
            :param vName: the vehichle name that is being ride-matched
            :type vName: str of vehichle name
            :param queue: a queue of the ride requests to choose from
            :type queue: list of :class:`vehicle_server.Ride`

        :return: first ride or None if the queue is empty
        :rtype: :class:`vehicle_server.Ride` or None
        """
        match = None
        minDist = -1
        try:
            vlat,vlong = VehicleDBUtil.getVehicleLocation(SQLDB(), vName)
            origin = {'latitude': float(vlat), 'longitude': float(vlong)}
            checkLen = self.NUM_CHECK
            if len(queue) < self.NUM_CHECK:
                checkLen = len(queue)
            for i in range(0,checkLen):
                ride = queue[i]
                skips = self.rideSkip.get(ride.rideID)
                if skips == None:
                    self.rideSkip[ride.rideID] = 1
                elif skips >= self.SKIP_MAX:
                    queue.remove(ride)
                    self.rideSkip.pop(ride.rideID)
                    return ride
                elif skips < self.SKIP_MAX:
                    skips += 1
                    self.rideSkip[ride.rideID] = skips

            for i in range(0, checkLen):
                ride = queue[i]
                dest = {'latitude': float(ride.riderLat), 'longitude': float(ride.riderLon)}
                respon = googlemaps_util.sendGoogleDirectionsRequest(origin, dest)
                legs = json.loads(respon.text)['routes'][0]['legs']
                dist = 0
                for leg in legs:
                    dist += leg['distance']['value']
                print(dist)
                if (i == 0) or (minDist > dist):
                    minDist = dist
                    match = ride
            queue.remove(match)
            self.rideSkip.pop(match.rideID)
            return match
        except IndexError:
            return None
        except ValueError:
            return None


class VehicleRideSelector():
    """The Factory class providing an instance of :class:`vehicle_util.VehicleSelectorStrategy` based on fleet condition

    The class contains a list of existing strategies and makes a selection of the strategy that provides optimal utilization
    of fleet resources and maximum riders satisfaction.
    In other words, it examines the fleet conditions and ride requests and chooses the optimal strategy from the available selection

    :param _strategies: the private map of a strategy keyword to a strategy class. Used to keep track of all available strategies
    :type _strategies: dict
    :param _default: the default strategy
    :param _default: str
    """
    def __init__(self) -> None:
        """Constructor method
        """
        self._strategies = {
            "fifo": FIFORide,
            "prox": ProximityRide
        }
        self._default = "fifo"

    def getVehicleSelector(self, strategy: Optional[str] = None) -> VehicleSelectorStrategy:
        """Selects an instance of the :class:`vehicle_util.VehicleSelectorStrategy` that represents the best strategy for the conditions

        :param strategy: An optional parameter that allows the caller to specify which strategy to use by providing its name
        :type strategy: str

        :return: an instance of the strategy for selecting a ride
        :rtype: VehicleSelectorStrategy
        """
        try:
            return self._strategies[strategy]()
        except KeyError:
            if(strategy != None):
                print("ERROR: No strategy named %s. Using %s." % (strategy, self._default))
        return self._strategies[self._default]()
