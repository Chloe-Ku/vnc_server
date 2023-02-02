#
# This class represents an abstraction for a would-be robot.
# It maintains an internal belief about the world
# (which will eventualy be gotten with real-life robot sensors),
# and upates that belief accordingly.
#

import random
import threading


class Vehicle(object):

    # How close a vehicle can be and be considered 'at' a location (meters)
    proximityAllowed = 5.0

    @staticmethod
    def genVehicle():
        nRandomLetters = 5
        alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        randPart = ''.join(random.choice(alphabet)
                           for _i in range(nRandomLetters))
        name = 'Vehicle %s' % randPart

        # These are the coordinates of the base station. However, before communication with the 
        # server is ever initialized the callback function from the VehicleOdomInfo subscriber
        # will replace the latitude and longitude coordinates with the true location
        baseLat = 35.768664
        baseLon = -78.677591

        return Vehicle(name, baseLat, baseLon)

    #Initialize our Vehicle with a unique name, latitude/longitude position, heading angle, steering angle, speed, and battery life.
    #These states will be updated by comm_strategy as parts of callback functions to the VehicleOdomInfo topic
    def __init__(self, name, lat, lon):
        """
        lat is latitude (in degrees)
        lon is longitude (in degress)
        heading  is degrees from true north (positive clockwise)
        steering is degrees from true north (positive clockwise)
        speed is meters per second
        """

        # Instantiate the Vehicle with zero equivalent values for heading, steering, speed, & battery life. These will be
        # updated by subscriber call back functions from the /ecoprt/VehicleOdomInfo topic before communication with the 
        # server is initialized
        self.name = name
        self.lat = lat
        self.lon = lon
        self.heading = 0.0  # True north (90.0 would be true east)
        self.steering = 0.0
        self.speed = 0.0
        self.batteryLife = 99

        # Create a thread lock. Don't want our callback functions editing the Vehicle state while our main thread in comm_strategy
        # tries to read them
        self.sensorsLock = threading.Lock()

    #Thread safe getters and setters for our callback functions and thread main to use to access Vehicle state

    def getDict(self):
        with self.sensorsLock:
            return self.__dict__

    def getName(self):
        with self.sensorsLock:
            return self.name

    def setSpeed(self, speed):
        with self.sensorsLock:
            self.speed = speed

    def getSpeed(self):
        with self.sensorsLock:
            return self.speed

    def setHeading(self, heading):
        with self.sensorsLock:
            self.heading = heading

    def getHeading(self):
        with self.sensorsLock:
            return self.heading

    def setSteering(self, steering):
        with self.sensorsLock:
            self.steering = steering

    def getSteering(self):
        with self.sensorsLock:
            return self.steering

    def setBatteryLife(self, batteryLife):
        with self.sensorsLock:
            self.batteryLife = batteryLife

    def getBatteryLife(self):
        with self.sensorsLock:
            return self.batteryLife

    #Return the current latitude and longitude position of this vehicle in a (lat, lon) tuple
    def getLocation(self):
        with self.sensorsLock:
            return (self.lat, self.lon)

    #Update the current latitude and longitude position of this Vehicle
    def setLocation(self, lat, lon):
        with self.sensorsLock:
            self.lat = lat
            self.lon = lon