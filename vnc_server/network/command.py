#
# This file defines commands between the client and server.
#
# It uses Communication internally.
# Note that, while Communication seralizes a Python object to a string,
# Command 'serializes' an instance of a class to a Python object.
#
#

#
# abstractmethod decorator reuqires the function to be implemented
# in its base classes.
#
from abc import abstractmethod

from communication import Communication


class Command():
    """
    The base, abstract Command class.
    All Commands inherit from Command.

    Usually, a Command will have a static list of fields,
    and each instance has those attributes.

    However, sometimes things get complicated.
    The programmer may want to either extend or completely override:
    __init__(), toObj(), fromObj(), __str__(), etc.
    Really, any function EXCEPT send() and recv().
    Just make sure to be smart about extending/overriding.

    Usage example:

    # On the client
    initAck = InitAck({'lat': 71, 'lon': 72})
    initAck.send(sock)

    # On the server
    initAck = Command.recv(self.sock)
    print(initAck)
    """

    # Recommended amount of time to sleep after a request/ack
    sleepTime = 0.50

    #
    # Update this instance's fields to agree with the input object
    #

    def __init__(self, obj={}):
        for f in self.__class__.fields:
            self.__dict__[f] = obj[f]

    #
    # Return the object representation of this instance's fields.
    #

    def toObj(self):
        return {
            f: self.__dict__[f] for f in self.__class__.fields
        }

    #
    # Each Command should know how to create an instance of itself
    # from an object that represents it.
    #
    # In order for this function to remain in the abstract base class Command,
    # it needs to be passed the concrete class
    # (even though the caller will already know the concrete class).
    #

    @staticmethod
    def fromObj(concreteClass, obj):
        return concreteClass(obj)

    #
    # String representation of the fields for the given class.
    #

    def __str__(self):
        out = '%s{' % self.__class__.__name__
        out += ', '.join(['%s=%s' % (f, self.__dict__[f])
                          for f in self.__class__.fields])
        out += '}'

        return out

    #
    # Do NOT override this function.
    #
    # Send the object representing this command over a socket.
    # Always add the class name.
    # NOTE: If a Command uses className, it will get clobbered.
    #

    def send(self, sock):
        objToSend = self.toObj()
        objToSend['className'] = self.__class__.__name__
        Communication.sendObject(sock, objToSend)

    #
    # Do NOT override this function.
    #
    # Get an instance of the Command represented by the given object.
    #

    @staticmethod
    def recv(sock):
        obj = Communication.recvObject(sock)
        # print('Command.recv(%s)' % obj)

        if (obj == None):
            raise Exception('Received object was None')

        if ('className' not in obj):
            raise Exception('Received object has no className field: %s' % obj)

        commandClass = eval(obj['className'])
        if (not issubclass(commandClass, Command) or commandClass == Command):
            raise Exception(
                'Class must be subclass of Command, and not Command itself: %s' % obj)

        # fromObj() is abstract, so it must be implemented
        return commandClass.fromObj(commandClass, obj)


# SERVER COMMANDS BELOW

# Server: Acknowledge the initialization request of the Client
class InitAck(Command):
    fields = [
        
    ]

# Server: Idle --> Idle
# No information required because there is no transition
class IdleRequest(Command):
    fields = []


# Server: Idle --> EnrouteToRider
# Server sends this Command to the Client to transition it from IDLE to ENROUTE_TO_RIDER
class IdleToEnrouteToRiderRequest(Command):
    fields = [
        # Server sends the latitude/longitude coordinates of the rider to the vehicle
        'lat', 
        'lon'
    ]

# Server: ToRider -> EnrouteToDest
# Server sends this Command to the Client to transition it from TO_RIDER to ENROUTE_TO_DEST
# Occurs when confirmPickup is called
class ToRiderToEnrouteToDestRequest(Command):
    fields = [
        # Server sends the latitude/longitude coordinates of the rider to the vehicle
        'lat', 
        'lon'
    ]

# Server: ToDest -> Idle
# Server sends this Command to the Client to transition it from TO_DEST to IDLE
# Occurs when confirmArrival is called
class ToDestToIdle(Command):
    fields = [
        # Server sends the latitude/longitude coordinates of the rider to the vehicle
        'lat', 
        'lon'
    ]

# Server: ToRider -> Idle
# Server sends this Command to the Client to transition it from TO_RIDER to IDLE
# Occurs when ride is canceled and vehicle is in the first half of its trip (heading towards rider)
class ToRiderCancel(Command):
    fields = [
        # Server sends the latitude/longitude coordinates of the rider to the vehicle
        'lat', 
        'lon'
    ]

# Server: ToDest -> Idle
# Server sends this Command to the Client to transition it from TO_DEST to IDLE
# Occurs when ride is canceled and vehicle is in the second half of its trip (heading towards destination)
class ToDestCancel(Command):
    fields = [
        # Server sends the latitude/longitude coordinates of the rider to the vehicle
        'lat', 
        'lon'
    ]

# Server: Idle -> Enroute To Charger
# Server sends this Command to the Client to transition it from IDLE to ENROUTE_TO_CHARGER
class IdleToEnrouteToCharger(Command):
    fields = [
        # Server sends the latitude/longitude coordinates of the charging station to the vehicle
        'lat', 
        'lon'
    ]

# Server: Enroute To Charger -> Charging
# Server sends this Command to the Client to transition it from ENROUTE_TO_CHARGER to CHARGING
# Occurs when vehicle
class EnrouteToChargerToCharging(Command):
    fields = [
        # Server sends the latitude/longitude coordinates of the charging station to the vehicle
        'lat', 
        'lon'
    ]

# Server: Charging -> Charging
# Server sends this Command to the Client to transition it from Charging to CHARGING
# Occurs when vehicle
class ChargingToCharging(Command):
    fields = [
        # Server sends the latitude/longitude coordinates of the charging station to the vehicle
        'lat', 
        'lon'
    ]

# Server: Charging -> Idle
# Server sends this Command to the Client to transition it from CHARING to IDLE
class ChargingToIdle(Command):
    fields = [
        # Server sends the latitude/longitude coordinates of the charging station to the vehicle
        'lat', 
        'lon'
    ]

# CLIENT COMMANDS BELOW

# Client: Register with the server
# To register the vehicle with the Vehicle Server.
class InitRequest(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'mileage'
    ]

# Client: Idle --> Idle
# Client sends this Command to the Server while it is spinning in the IDLE state
class IdleAck(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'mileage'
    ]

# Client: Idle --> EnrouteToRider
# Client sends this Command to the Server when it transitions from the IDLE state to the ENROUTE_TO_RIDER state
class IdleToEnrouteToRiderAck(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'mileage'
    ]

# Client: EnrouteToRider -> EnrouteToRider
# Client sends this Command to the Server while it is spinning in the ENROUTE_TO_RIDER state
class EnrouteToRiderAck(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'mileage'
    ]


# Client: EnrouteToRider -> ToRider
# Client sends this Command to the Server when it transitions from the ENROUTE_TO_RIDER state to the TO_RIDER state
class EnrouteToRiderToToRiderAck(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'mileage'
    ]

# Client: ToRider -> EnrouteToDest
# Client sends this Command to the Server when it transitions from the TO_RIDER state to the ENROUTE_TO_DEST state
class ToRiderToEnrouteToDestAck(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'mileage'
    ]

# Client: EnrouteToDest -> EnrouteToDest
# Client sends this Command to the Server while it is spinning in the ENROUTE_TO_DEST state
class EnrouteToDestAck(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'mileage'
    ]


# Client: EnrouteToDest -> ToDest
# Client sends this Command to the Server when it transitions from the ENROUTE_TO_DEST state to the TO_DEST state
class EnrouteToDestToToDestAck(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'mileage'
    ]

# Client: ToDest -> Idle
# Client sends this Command to the Server when it transitions from the TO_DEST state to the IDLE state
class ToDestToIdleAck(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'mileage'
    ]

# Client: ToRider -> Idle
# Client sends this Command to the Server when it transitions from the TO_RIDER state to the IDLE state
class ToRiderCancelAck(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'mileage'
    ]

# Client: ToDest -> Idle
# Client sends this Command to the Server when it transitions from the TO_DEST state to the IDLE state
class ToDestCancelAck(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'mileage'
    ]

# Client: Idle -> Enroute to Charger
# Client sends this Command to the Server when it transitions from the IDLE state to the ENROUTE_TO_CHARGER state
class IdleToEnrouteToChargerAck(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'targetBatteryLife',
        'mileage'
    ]

# Client: Enroute to Charger -> Charging
# Client sends this Command to the Server when it transitions from the ENROUTE_TO_CHARGER state to the CHARGING state
class EnrouteToChargerToChargingAck(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'targetBatteryLife',
        'mileage'
    ]

# Client: Charging -> Idle
# Client sends this Command to the Server when it transitions from the CHARGING state to the IDLE state
class ChargingToIdleAck(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'targetBatteryLife',
        'mileage'
    ]

# Client: EnrouteToCharger -> EnrouteToCharger
# Client sends this Command to the Server while it is spinning in the ENROUTE_TO_CHARGER state
class EnrouteToChargerAck(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'targetBatteryLife',
        'mileage'
    ]

# Client: Charging -> Charging
# Client sends this Command to the Server while it is spinning in the CHARGING state
class ChargingAck(Command):
    fields = [
        'name',
        'lat',
        'lon',
        'heading',
        'steering',
        'speed',
        'batteryLife',
        'minBatteryLife',
        'targetBatteryLife',
        'mileage'
    ]

#
# Server to Client.
#
class SendRequest(Command):
    fields = [
        'lat',
        'lon'
    ]


#
# Client to Server.
#
class SendAck(Command):
    fields = [
        'lat',
        'lon'
    ]


def main():
    # myCommand = InitRequest(5)
    # print('My command: %s' % myCommand.toObj())
    # myCommand.send('Socket would go here')
    print(InitRequest)
    print(type(InitRequest).__name__)

    something = eval('InitRequest')
    print(something)
    print(type(something).__name__)


# For testing purposes
if __name__ == '__main__':
    main()
